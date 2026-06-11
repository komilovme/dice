"""User lifecycle and profile aggregation service."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import User as TgUser

from app.config.constants import RANK_TIERS, Rank, TransactionType
from app.config.settings import settings
from app.models.user import User
from app.repositories.achievement_repository import AchievementRepository
from app.repositories.clan_repository import ClanRepository
from app.repositories.user_repository import UserRepository
from app.services.anticheat_service import AntiCheatService
from app.services.base import BaseService
from app.services.economy_service import EconomyService
from app.services.ranking_service import RankingService


@dataclass(slots=True)
class ProfileView:
    user: User
    rank_icon: str
    achievements_unlocked: int
    achievements_total: int
    clan_name: str | None
    xp_into: int
    xp_needed: int


class UserService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.users = UserRepository(session)
        self.achievements = AchievementRepository(session)
        self.clans = ClanRepository(session)

    async def get_or_create(
        self, tg_user: TgUser, *, referrer_telegram_id: int | None = None
    ) -> tuple[User, bool]:
        """Return (user, created). Creates the user and handles referrals once."""
        existing = await self.users.get_by_telegram_id(tg_user.id)
        if existing is not None:
            await self._sync_profile_fields(existing, tg_user)
            return existing, False

        referrer = None
        if referrer_telegram_id and referrer_telegram_id != tg_user.id:
            referrer = await self.users.get_by_telegram_id(referrer_telegram_id)

        user = await self.users.create(
            telegram_id=tg_user.id,
            username=tg_user.username,
            first_name=tg_user.first_name,
            last_name=tg_user.last_name,
            language_code=tg_user.language_code,
            starting_balance=settings.starting_balance,
            referrer_id=referrer.id if referrer else None,
            is_admin=settings.is_admin(tg_user.id),
        )

        economy = EconomyService(self.session, self.redis)
        await economy.grant_signup_bonus(user.id)

        if referrer is not None:
            await self._reward_referral(referrer, user, economy)

        return user, True

    async def _reward_referral(
        self, referrer: User, new_user: User, economy: EconomyService
    ) -> None:
        await economy.credit(
            referrer.id,
            settings.referral_reward,
            type=TransactionType.REFERRAL_REWARD,
            description=f"Referred {new_user.display_name}",
            reference=str(new_user.id),
        )
        await economy.credit(
            new_user.id,
            settings.referral_reward // 2,
            type=TransactionType.REFERRAL_REWARD,
            description="Joined via referral",
        )
        await self.users.increment_referrals(referrer.id)
        anticheat = AntiCheatService(self.session, self.redis)
        await anticheat.detect_referral_farm(referrer.id)

    async def _sync_profile_fields(self, user: User, tg_user: TgUser) -> None:
        """Keep cached Telegram profile fields fresh on each interaction."""
        changed = False
        for field, value in (
            ("username", tg_user.username),
            ("first_name", tg_user.first_name),
            ("last_name", tg_user.last_name),
        ):
            if getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if changed:
            await self.session.flush()

    async def build_profile(self, user: User) -> ProfileView:
        unlocked = await self.achievements.unlocked_codes(user.id)
        membership = await self.clans.get_membership(user.id)
        xp_into, xp_needed = RankingService.progress_to_next(user)
        icon = next((t.icon for t in RANK_TIERS if t.rank == Rank(user.rank)), "🥉")
        from app.config.constants import ACHIEVEMENTS

        return ProfileView(
            user=user,
            rank_icon=icon,
            achievements_unlocked=len(unlocked),
            achievements_total=len(ACHIEVEMENTS),
            clan_name=membership.clan.name if membership else None,
            xp_into=xp_into,
            xp_needed=xp_needed,
        )
