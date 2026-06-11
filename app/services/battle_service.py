"""Dice battle orchestration across all game modes.

Responsibilities:
  * Create battles (duel, friend, public, group, team, royale, jackpot, tournament)
  * Take stakes safely and refund on cancellation
  * Record dice rolls (Telegram-authoritative in groups, CSPRNG elsewhere)
  * Settle battles: determine winners, split the pot minus house edge, apply
    powerups, update stats / streaks / XP / season points, fire achievements,
    and produce the announcer line + a clean result payload for the handler.

The settlement is written to be N-player so it serves duels, royales and
jackpots with the same code path.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import update

from app.config.constants import (
    BattleMode,
    BattleStatus,
    PowerupType,
    TransactionType,
)
from app.config.settings import settings
from app.models.battle import Battle, BattleParticipant
from app.models.user import User
from app.repositories.battle_repository import BattleRepository
from app.repositories.inventory_repository import PowerupRepository
from app.repositories.season_repository import SeasonRepository
from app.repositories.stats_repository import StatsRepository
from app.repositories.user_repository import UserRepository
from app.services.announcer_service import AnnouncerContext, AnnouncerService
from app.services.base import BaseService
from app.services.economy_service import EconomyService
from app.services.ranking_service import RankingService, xp_for_outcome
from app.utils.dice import roll_dice, score_from_telegram_value
from app.utils.exceptions import NotFoundError, ValidationError

# Default dice rolled per player for a standard duel.
DEFAULT_DICE_PER_PLAYER = 2
SEASON_POINTS_WIN = 50
SEASON_POINTS_PARTICIPATE = 10


class DiceRollOutcome(enum.StrEnum):
    NO_BATTLE = "no_battle"
    JOINED = "joined"
    ROLLED = "rolled"
    ALREADY_ROLLED = "already_rolled"
    SPECTATOR = "spectator"
    WAITING = "waiting"
    SETTLED = "settled"


@dataclass(slots=True)
class ParticipantResult:
    user_id: int
    telegram_id: int
    display_name: str
    score: int
    rolls: list[int]
    is_winner: bool
    payout: int
    net: int


@dataclass(slots=True)
class BattleSettlement:
    battle_id: int
    mode: BattleMode
    pot: int
    house_cut: int
    is_draw: bool
    participants: list[ParticipantResult]
    announcer_message: str
    winner_streak: int = 0
    unlocked: dict[int, list] = field(default_factory=dict)  # user_id -> achievements
    promotions: dict[int, str] = field(default_factory=dict)  # user_id -> new rank

    @property
    def winners(self) -> list[ParticipantResult]:
        return [p for p in self.participants if p.is_winner]


@dataclass(slots=True)
class DiceRollResult:
    outcome: DiceRollOutcome
    battle: Battle | None = None
    settlement: BattleSettlement | None = None


class BattleService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.battles = BattleRepository(session)
        self.users = UserRepository(session)
        self.stats = StatsRepository(session)
        self.powerups = PowerupRepository(session)
        self.seasons = SeasonRepository(session)
        self.economy = EconomyService(session, redis)
        self.ranking = RankingService(session, redis)
        self.announcer = AnnouncerService()

    # ------------------------------------------------------------------
    # Creation / joining
    # ------------------------------------------------------------------
    async def create_battle(
        self,
        *,
        host: User,
        mode: BattleMode,
        stake: int,
        chat_id: int | None = None,
        max_players: int = 2,
        dice_per_player: int = DEFAULT_DICE_PER_PLAYER,
        is_team_mode: bool = False,
    ) -> Battle:
        """Create a battle and enrol the host, taking their stake up front."""
        season = await self.seasons.get_active()
        battle = await self.battles.create(
            mode=mode,
            stake=stake,
            created_by_id=host.id,
            season_id=season.id if season else None,
            chat_id=chat_id,
            is_team_mode=is_team_mode,
            status=BattleStatus.PENDING,
        )
        battle.extra = {
            "max_players": max_players,
            "dice_per_player": dice_per_player,
        }
        await self._take_stake(host, battle, team=0 if is_team_mode else None)
        await self.session.flush()
        return battle

    async def _take_stake(
        self, user: User, battle: Battle, *, team: int | None
    ) -> BattleParticipant:
        if battle.stake > 0:
            await self.economy.debit(
                user.id,
                battle.stake,
                type=TransactionType.BATTLE_STAKE,
                description=f"Stake for battle #{battle.id}",
                reference=str(battle.id),
                track_stats=False,
            )
            await self.session.execute(
                update(Battle).where(Battle.id == battle.id).values(pot=Battle.pot + battle.stake)
            )
            battle.pot += battle.stake
        return await self.battles.add_participant(battle.id, user.id, team=team)

    async def join_battle(self, *, user: User, battle: Battle) -> BattleParticipant:
        max_players = int(battle.extra.get("max_players", 2))
        if len(battle.participants) >= max_players:
            raise ValidationError("This battle is already full.")
        if any(p.user_id == user.id for p in battle.participants):
            raise ValidationError("You are already in this battle.")
        participant = await self._take_stake(user, battle, team=None)
        battle.participants.append(participant)
        return participant

    # ------------------------------------------------------------------
    # Group dice flow (feature 14)
    # ------------------------------------------------------------------
    async def active_battle_in_chat(self, chat_id: int) -> Battle | None:
        """Return the open group battle in a chat (if one is awaiting rolls)."""
        return await self.battles.find_active_in_chat(chat_id)

    async def register_dice_roll(
        self, *, chat_id: int, user: User, dice_value: int
    ) -> DiceRollResult:
        """Attach a Telegram dice roll to the active group battle in a chat.

        This drives the "clean group" experience: the handler deletes the raw
        dice message and posts a formatted result once the battle settles.
        """
        battle = await self.battles.find_active_in_chat(chat_id)
        if battle is None:
            return DiceRollResult(DiceRollOutcome.NO_BATTLE)

        dice_per_player = int(battle.extra.get("dice_per_player", DEFAULT_DICE_PER_PLAYER))
        max_players = int(battle.extra.get("max_players", 2))
        value = score_from_telegram_value(dice_value)

        participant = next((p for p in battle.participants if p.user_id == user.id), None)

        if participant is None:
            if len(battle.participants) >= max_players:
                return DiceRollResult(DiceRollOutcome.SPECTATOR, battle)
            participant = await self.join_battle(user=user, battle=battle)
            outcome = DiceRollOutcome.JOINED
        else:
            if participant.has_rolled:
                return DiceRollResult(DiceRollOutcome.ALREADY_ROLLED, battle)
            outcome = DiceRollOutcome.ROLLED

        # Record this die; mark complete once enough dice are gathered.
        participant.rolls = [*participant.rolls, value]
        participant.score = sum(participant.rolls)
        if len(participant.rolls) >= dice_per_player:
            participant.has_rolled = True
        await self.session.flush()

        ready = len(battle.participants) >= max_players and all(
            p.has_rolled for p in battle.participants
        )
        if ready:
            settlement = await self.settle(battle)
            return DiceRollResult(DiceRollOutcome.SETTLED, battle, settlement)

        return DiceRollResult(outcome, battle)

    async def roll_for(
        self, *, battle: Battle, user_id: int, dice_per_player: int | None = None
    ) -> BattleParticipant:
        """Roll dice via CSPRNG for non-group modes (inline duels, royale)."""
        participant = next((p for p in battle.participants if p.user_id == user_id), None)
        if participant is None:
            raise NotFoundError("You are not part of this battle.")
        count = dice_per_player or int(battle.extra.get("dice_per_player", DEFAULT_DICE_PER_PLAYER))
        participant.rolls = roll_dice(count)
        participant.score = sum(participant.rolls)
        participant.has_rolled = True
        await self.session.flush()
        return participant

    async def auto_resolve(self, battle: Battle) -> BattleSettlement:
        """Roll (via CSPRNG) for any participant who hasn't rolled, then settle.

        Used by lobby/matchmaking flows that resolve instantly and fairly.
        """
        count = int(battle.extra.get("dice_per_player", DEFAULT_DICE_PER_PLAYER))
        for p in battle.participants:
            if not p.has_rolled:
                p.rolls = roll_dice(count)
                p.score = sum(p.rolls)
                p.has_rolled = True
        await self.session.flush()
        return await self.settle(battle)

    # ------------------------------------------------------------------
    # Settlement
    # ------------------------------------------------------------------
    async def settle(self, battle: Battle) -> BattleSettlement:
        """Resolve a fully-rolled battle: pick winners, pay out, update state."""
        if battle.status == BattleStatus.FINISHED:
            raise ValidationError("Battle already settled.")

        participants = battle.participants
        top_score = max((p.score for p in participants), default=0)
        winners = [p for p in participants if p.score == top_score]
        is_draw = len(winners) == len(participants) or len(winners) > 1

        house_cut = 0
        results: list[ParticipantResult] = []
        unlocked: dict[int, list] = {}
        promotions: dict[int, str] = {}
        winner_streak = 0

        if is_draw:
            # Refund every participant their stake; no house edge on a draw.
            for p in participants:
                refund = battle.stake
                if refund:
                    await self.economy.credit(
                        p.user_id,
                        refund,
                        type=TransactionType.BATTLE_REFUND,
                        description=f"Draw refund battle #{battle.id}",
                        reference=str(battle.id),
                        track_stats=False,
                    )
                await self.stats.record_game_result(
                    p.user_id, won=False, draw=True, wagered=battle.stake, net_change=0
                )
                results.append(await self._participant_result(p, refund, 0))
            announcer_message = self.announcer.draw_message()
        else:
            house_cut = int(battle.pot * settings.house_edge)
            winner_pool = battle.pot - house_cut
            winner = winners[0]

            for p in participants:
                if p.user_id == winner.user_id:
                    payout = await self._pay_winner(battle, p, winner_pool)
                    net = payout - battle.stake
                    winner_streak = await self._bump_streak(p.user_id, won=True)
                    await self.stats.record_game_result(
                        p.user_id,
                        won=True,
                        draw=False,
                        wagered=battle.stake,
                        net_change=net,
                    )
                    results.append(await self._participant_result(p, payout, net))
                else:
                    refunded = await self._handle_loser(battle, p)
                    net = refunded - battle.stake
                    await self._bump_streak(p.user_id, won=False)
                    await self.stats.record_game_result(
                        p.user_id,
                        won=False,
                        draw=False,
                        wagered=battle.stake,
                        net_change=net,
                    )
                    results.append(await self._participant_result(p, refunded, net))

            announcer_message = await self._build_announcer(
                battle, winner, participants, winner_streak
            )
            if house_cut:
                await self.economy.transactions.record(
                    user_id=winner.user_id,
                    type=TransactionType.HOUSE_EDGE,
                    amount=-house_cut,
                    balance_after=0,
                    description=f"House edge battle #{battle.id}",
                    reference=str(battle.id),
                )

        # XP, season, achievements for every participant.
        for p in participants:
            won = (not is_draw) and p.user_id == winners[0].user_id
            await self._post_game_progression(
                battle,
                p,
                won=won,
                draw=is_draw,
                unlocked=unlocked,
                promotions=promotions,
            )

        await self._finalize_battle(battle, winners, is_draw, house_cut)

        return BattleSettlement(
            battle_id=battle.id,
            mode=BattleMode(battle.mode),
            pot=battle.pot,
            house_cut=house_cut,
            is_draw=is_draw,
            participants=results,
            announcer_message=announcer_message,
            winner_streak=winner_streak,
            unlocked=unlocked,
            promotions=promotions,
        )

    async def _pay_winner(self, battle: Battle, winner: BattleParticipant, winner_pool: int) -> int:
        payout = winner_pool
        # DOUBLE_REWARD powerup doubles the net winnings (bonus funded by house).
        dbl = await self.powerups.get(winner.user_id, PowerupType.DOUBLE_REWARD)
        if dbl is not None and dbl.charges > 0:
            net = payout - battle.stake
            payout += max(net, 0)
            await self.powerups.consume_charge(dbl.id)
            winner.powerups_used = [*winner.powerups_used, PowerupType.DOUBLE_REWARD]
        if payout:
            await self.economy.credit(
                winner.user_id,
                payout,
                type=TransactionType.BATTLE_WIN,
                description=f"Won battle #{battle.id}",
                reference=str(battle.id),
                track_stats=False,
            )
        winner.is_winner = True
        winner.payout = payout
        return payout

    async def _handle_loser(self, battle: Battle, loser: BattleParticipant) -> int:
        """Apply INSURANCE powerup (refund stake) if the loser has it."""
        ins = await self.powerups.get(loser.user_id, PowerupType.INSURANCE)
        if ins is not None and ins.charges > 0 and battle.stake:
            await self.economy.credit(
                loser.user_id,
                battle.stake,
                type=TransactionType.BATTLE_REFUND,
                description=f"Insurance refund battle #{battle.id}",
                reference=str(battle.id),
                track_stats=False,
            )
            await self.powerups.consume_charge(ins.id)
            loser.powerups_used = [*loser.powerups_used, PowerupType.INSURANCE]
            return battle.stake
        return 0

    async def _bump_streak(self, user_id: int, *, won: bool) -> int:
        user = await self.users.get(user_id)
        if user is None:
            return 0
        if won:
            user.current_streak += 1
            user.best_streak = max(user.best_streak, user.current_streak)
        else:
            protection = await self.powerups.get(user_id, PowerupType.STREAK_PROTECTION)
            if protection is not None and protection.charges > 0:
                await self.powerups.consume_charge(protection.id)
            else:
                user.current_streak = 0
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(
                current_streak=user.current_streak,
                best_streak=user.best_streak,
            )
        )
        return user.current_streak

    async def _participant_result(
        self, p: BattleParticipant, payout: int, net: int
    ) -> ParticipantResult:
        user = p.user if p.user is not None else await self.users.get(p.user_id)
        return ParticipantResult(
            user_id=p.user_id,
            telegram_id=user.telegram_id if user else 0,
            display_name=user.display_name if user else f"Player {p.user_id}",
            score=p.score,
            rolls=list(p.rolls),
            is_winner=p.is_winner,
            payout=payout,
            net=net,
        )

    async def _build_announcer(
        self,
        battle: Battle,
        winner: BattleParticipant,
        participants: list[BattleParticipant],
        winner_streak: int,
    ) -> str:
        loser_score = max(
            (p.score for p in participants if p.user_id != winner.user_id),
            default=0,
        )
        dice_per_player = int(battle.extra.get("dice_per_player", DEFAULT_DICE_PER_PLAYER))
        ctx = AnnouncerContext(
            winner_score=winner.score,
            loser_score=loser_score,
            dice_per_player=dice_per_player,
            winner_streak=winner_streak,
            is_new_streak_leader=winner_streak >= 5,
        )
        return self.announcer.announce(ctx)

    async def _post_game_progression(
        self,
        battle: Battle,
        p: BattleParticipant,
        *,
        won: bool,
        draw: bool,
        unlocked: dict,
        promotions: dict,
    ) -> None:
        user = await self.users.get_with_stats(p.user_id)
        if user is None:
            return
        # XP + rank.
        xp = xp_for_outcome(won=won, draw=draw, pot=battle.pot)
        xp_result = await self.ranking.award_xp(user, xp)
        if xp_result.promoted:
            promotions[p.user_id] = xp_result.new_rank

        # Season points.
        if battle.season_id is not None:
            await self.seasons.add_points(
                season_id=battle.season_id,
                user_id=p.user_id,
                points=SEASON_POINTS_WIN if won else SEASON_POINTS_PARTICIPATE,
                won=won,
                coins=max(p.payout - battle.stake, 0),
            )

        # Achievements (lazy import avoids a circular dependency).
        from app.services.achievement_service import AchievementService

        achievements = AchievementService(self.session, self.redis)
        newly = await achievements.evaluate(user)
        if newly:
            unlocked[p.user_id] = newly

    async def _finalize_battle(
        self,
        battle: Battle,
        winners: list[BattleParticipant],
        is_draw: bool,
        house_cut: int,
    ) -> None:
        await self.session.execute(
            update(Battle)
            .where(Battle.id == battle.id)
            .values(
                status=BattleStatus.FINISHED,
                finished_at=datetime.now(UTC),
                house_cut=house_cut,
                winner_id=None if is_draw else winners[0].user_id,
            )
        )
        battle.status = BattleStatus.FINISHED

    # ------------------------------------------------------------------
    # Solo play vs the house (used for private-chat quick duels)
    # ------------------------------------------------------------------
    async def play_solo_vs_house(
        self, *, user: User, stake: int, dice_per_player: int = DEFAULT_DICE_PER_PLAYER
    ) -> BattleSettlement:
        """Resolve an instant PvE duel against the house using a CSPRNG.

        Used in private chat where there is no human opponent. The house edge is
        applied to winnings; ties refund the stake.
        """
        season = await self.seasons.get_active()
        battle = await self.battles.create(
            mode=BattleMode.DUEL,
            stake=stake,
            created_by_id=user.id,
            season_id=season.id if season else None,
            status=BattleStatus.ROLLING,
        )
        battle.extra = {
            "max_players": 1,
            "dice_per_player": dice_per_player,
            "vs_house": True,
        }
        if stake > 0:
            await self.economy.debit(
                user.id,
                stake,
                type=TransactionType.BATTLE_STAKE,
                description=f"Stake for solo battle #{battle.id}",
                reference=str(battle.id),
                track_stats=False,
            )
            battle.pot = stake

        participant = await self.battles.add_participant(battle.id, user.id)
        user_rolls = roll_dice(dice_per_player)
        participant.rolls = user_rolls
        participant.score = sum(user_rolls)
        participant.has_rolled = True

        house_rolls = roll_dice(dice_per_player)
        house_score = sum(house_rolls)
        await self.session.flush()

        won = participant.score > house_score
        draw = participant.score == house_score

        payout = 0
        net = -stake
        winner_streak = 0
        if draw:
            if stake:
                await self.economy.credit(
                    user.id,
                    stake,
                    type=TransactionType.BATTLE_REFUND,
                    description=f"Draw refund battle #{battle.id}",
                    reference=str(battle.id),
                    track_stats=False,
                )
            net = 0
            await self.stats.record_game_result(
                user.id, won=False, draw=True, wagered=stake, net_change=0
            )
        elif won:
            house_cut = int(stake * 2 * settings.house_edge)
            payout = stake * 2 - house_cut
            participant.is_winner = True
            participant.payout = payout
            if payout:
                await self.economy.credit(
                    user.id,
                    payout,
                    type=TransactionType.BATTLE_WIN,
                    description=f"Won solo battle #{battle.id}",
                    reference=str(battle.id),
                    track_stats=False,
                )
            net = payout - stake
            winner_streak = await self._bump_streak(user.id, won=True)
            await self.stats.record_game_result(
                user.id, won=True, draw=False, wagered=stake, net_change=net
            )
        else:
            await self._bump_streak(user.id, won=False)
            await self.stats.record_game_result(
                user.id, won=False, draw=False, wagered=stake, net_change=net
            )

        unlocked: dict[int, list] = {}
        promotions: dict[int, str] = {}
        await self._post_game_progression(
            battle,
            participant,
            won=won,
            draw=draw,
            unlocked=unlocked,
            promotions=promotions,
        )
        await self._finalize_battle(battle, [participant] if won else [], draw or not won, 0)

        # Build a settlement with a synthetic "House" opponent for rendering.
        if draw:
            announcer_message = self.announcer.draw_message()
        else:
            ctx = AnnouncerContext(
                winner_score=max(participant.score, house_score),
                loser_score=min(participant.score, house_score),
                dice_per_player=dice_per_player,
                winner_streak=winner_streak,
            )
            announcer_message = self.announcer.announce(ctx)

        results = [
            ParticipantResult(
                user_id=user.id,
                telegram_id=user.telegram_id,
                display_name=user.display_name,
                score=participant.score,
                rolls=user_rolls,
                is_winner=won,
                payout=payout,
                net=net,
            ),
            ParticipantResult(
                user_id=0,
                telegram_id=0,
                display_name="🏠 House",
                score=house_score,
                rolls=house_rolls,
                is_winner=(not won and not draw),
                payout=0,
                net=0,
            ),
        ]
        return BattleSettlement(
            battle_id=battle.id,
            mode=BattleMode.DUEL,
            pot=battle.pot,
            house_cut=0,
            is_draw=draw,
            participants=results,
            announcer_message=announcer_message,
            winner_streak=winner_streak,
            unlocked=unlocked,
            promotions=promotions,
        )

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------
    async def cancel_battle(self, battle: Battle, reason: str = "cancelled") -> None:
        """Refund all stakes and mark the battle cancelled."""
        for p in battle.participants:
            if battle.stake:
                await self.economy.credit(
                    p.user_id,
                    battle.stake,
                    type=TransactionType.BATTLE_REFUND,
                    description=f"Refund: {reason} battle #{battle.id}",
                    reference=str(battle.id),
                    track_stats=False,
                )
        await self.session.execute(
            update(Battle)
            .where(Battle.id == battle.id)
            .values(status=BattleStatus.CANCELLED, finished_at=datetime.now(UTC))
        )
        battle.status = BattleStatus.CANCELLED
