"""Battle handlers.

Covers three entry points:
  * ``/duel [bet]`` in a group  → opens a group battle; players settle it by
    sending the 🎲 dice emoji (feature 14, group optimization).
  * The group dice listener      → reads the Telegram-authoritative dice value,
    deletes the raw dice message to keep the chat clean, and posts a single
    formatted result when the battle is decided.
  * Private quick duel (PvE)      → instant duel against the house.
"""

from __future__ import annotations

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import BattleMode
from app.config.logging import get_logger
from app.config.settings import settings
from app.filters.chat_type import ChatTypeFilter
from app.handlers.texts import render_settlement
from app.keyboards.callbacks import BattleCB
from app.keyboards.inline import back_to_menu
from app.models.user import User
from app.services.anticheat_service import AntiCheatService
from app.services.battle_service import BattleService, DiceRollOutcome
from app.utils.exceptions import GameError

logger = get_logger(__name__)
router = Router(name="battles")

DEFAULT_QUICK_BET = 100


def _parse_bet(text: str | None, default: int) -> int:
    if not text:
        return default
    parts = text.split()
    if len(parts) >= 2 and parts[1].lstrip("-").isdigit():
        return int(parts[1])
    return default


async def _pre_battle_checks(anticheat: AntiCheatService, user: User, stake: int) -> None:
    anticheat.ensure_not_banned(user)
    anticheat.validate_bet(stake)
    await anticheat.enforce_battle_cooldown(user.id)
    await anticheat.enforce_daily_battle_cap(user.id)


# ---------------------------------------------------------------------------
# Group duel: /duel [bet]
# ---------------------------------------------------------------------------
@router.message(Command("duel"), ChatTypeFilter({"group", "supergroup"}))
async def cmd_group_duel(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    stake = _parse_bet(message.text, settings.min_bet)
    anticheat = AntiCheatService(session, redis)
    battles = BattleService(session, redis)
    try:
        await _pre_battle_checks(anticheat, user, stake)
        battle = await battles.active_battle_in_chat(message.chat.id)
        if battle is not None:
            await message.answer("⚔️ There is already an open battle in this chat. Send 🎲 to play!")
            return
        await battles.create_battle(
            host=user,
            mode=BattleMode.GROUP,
            stake=stake,
            chat_id=message.chat.id,
            max_players=2,
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return

    await message.answer(
        f"🎲 <b>Dice Battle opened by {user.display_name}!</b>\n\n"
        f"Stake: <b>{stake:,}</b> coins each\n"
        f"Both players: send the 🎲 emoji to roll. First valid rolls settle it!"
    )


# ---------------------------------------------------------------------------
# Group dice listener (the clean-group flow)
# ---------------------------------------------------------------------------
@router.message(F.dice.as_("dice"), ChatTypeFilter({"group", "supergroup"}))
async def on_group_dice(
    message: Message,
    user: User,
    session: AsyncSession,
    redis: Redis,
    bot: Bot,
) -> None:
    dice = message.dice
    # Only the standard game die counts; ignore darts/basketball/etc.
    if dice is None or dice.emoji != "🎲":
        return

    battles = BattleService(session, redis)
    try:
        result = await battles.register_dice_roll(
            chat_id=message.chat.id, user=user, dice_value=dice.value
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return

    if result.outcome == DiceRollOutcome.NO_BATTLE:
        return  # leave casual dice alone

    # From here the dice belongs to a battle → remove it to keep the chat clean.
    await _safe_delete(message)

    if result.outcome == DiceRollOutcome.SPECTATOR:
        return
    if result.outcome == DiceRollOutcome.ALREADY_ROLLED:
        return

    if result.outcome == DiceRollOutcome.SETTLED and result.settlement is not None:
        await message.answer(render_settlement(result.settlement))
        return

    # Joined / rolled but waiting for the opponent.
    await message.answer(f"🎲 {user.display_name} rolled! Waiting for the other player…")


async def _safe_delete(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        # The bot may lack delete permission; degrade gracefully.
        logger.debug("dice_delete_failed", chat_id=message.chat.id)


# ---------------------------------------------------------------------------
# Private quick duel (PvE vs house)
# ---------------------------------------------------------------------------
async def _do_quick_duel(user: User, session: AsyncSession, redis: Redis, stake: int) -> str:
    anticheat = AntiCheatService(session, redis)
    battles = BattleService(session, redis)
    await _pre_battle_checks(anticheat, user, stake)
    settlement = await battles.play_solo_vs_house(user=user, stake=stake)
    return render_settlement(settlement)


@router.message(Command("play"), ChatTypeFilter("private"))
async def cmd_quick_duel(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    stake = _parse_bet(message.text, DEFAULT_QUICK_BET)
    try:
        text = await _do_quick_duel(user, session, redis, stake)
    except GameError as exc:
        text = f"⚠️ {exc.message}"
    await message.answer(text, reply_markup=back_to_menu())


@router.callback_query(BattleCB.filter(F.action == "quick"))
async def cb_quick_duel(
    query: CallbackQuery, user: User, session: AsyncSession, redis: Redis
) -> None:
    try:
        text = await _do_quick_duel(user, session, redis, DEFAULT_QUICK_BET)
    except GameError as exc:
        text = f"⚠️ {exc.message}"
    await query.message.answer(text)
    await query.answer()


@router.callback_query(BattleCB.filter(F.action == "public"))
async def cb_public(query: CallbackQuery) -> None:
    await query.answer()
    await query.message.answer(
        "🌐 <b>Public Battles</b>\n\n"
        "Use /lobby &lt;bet&gt; to open a public lobby others can join, or "
        "/join &lt;code&gt; to enter one. In a group, just use /duel &lt;bet&gt; "
        "and send 🎲.",
        reply_markup=back_to_menu(),
    )
