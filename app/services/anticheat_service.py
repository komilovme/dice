"""Anti-cheat & abuse-prevention service.

Combines fast Redis-backed checks (flood protection, cooldowns, daily caps) with
persistent flagging in PostgreSQL for audit and escalation. Bet-limit validation
and basic duplicate-account / referral-farm heuristics live here too.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update

from app.config.settings import settings
from app.models.user import User
from app.repositories.admin_repository import AntiCheatRepository
from app.services.base import BaseService
from app.utils.exceptions import BetLimitError, CooldownError, UserBannedError

# Suspicion score at which an account is auto-restricted from high-stakes play.
SUSPICION_SOFT_LIMIT = 50
SUSPICION_HARD_LIMIT = 100


class AntiCheatService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = AntiCheatRepository(session)

    # ------------------------------------------------------------------
    # Fast Redis checks
    # ------------------------------------------------------------------
    async def enforce_rate_limit(
        self, user_id: int, action: str, *, limit: int, window: int
    ) -> None:
        """Sliding fixed-window rate limit. Raises CooldownError when exceeded."""
        if self.redis is None:
            return
        key = f"rl:{action}:{user_id}"
        count = await self._incr(key, window)
        if count > limit:
            ttl = await self.redis.ttl(key)
            raise CooldownError(max(ttl, 1), action)

    async def enforce_cooldown(self, user_id: int, action: str, seconds: int) -> None:
        """Hard cooldown: only one ``action`` allowed per ``seconds``."""
        if self.redis is None:
            return
        key = f"cd:{action}:{user_id}"
        # SET NX EX returns None if the key already exists (still cooling down).
        ok = await self.redis.set(key, "1", ex=seconds, nx=True)
        if not ok:
            ttl = await self.redis.ttl(key)
            raise CooldownError(max(ttl, 1), action)

    async def enforce_battle_cooldown(self, user_id: int) -> None:
        await self.enforce_cooldown(user_id, "battle", settings.battle_cooldown_seconds)

    async def enforce_daily_battle_cap(self, user_id: int) -> None:
        if self.redis is None:
            return
        key = f"dailybattles:{user_id}:{datetime.now(UTC):%Y%m%d}"
        count = await self._incr(key, 86_400)
        if count > settings.max_daily_battles:
            await self.flag(
                user_id,
                rule="daily_battle_cap",
                severity=5,
                description=f"Exceeded daily battle cap ({count}).",
            )
            raise CooldownError(3_600, "battles (daily limit reached)")

    async def _incr(self, key: str, ttl: int) -> int:
        pipe = self.redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, ttl, nx=True)
        result = await pipe.execute()
        return int(result[0])

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    @staticmethod
    def validate_bet(amount: int) -> None:
        if amount < settings.min_bet:
            raise BetLimitError(f"Minimum bet is {settings.min_bet:,} coins.")
        if amount > settings.max_bet:
            raise BetLimitError(f"Maximum bet is {settings.max_bet:,} coins.")

    @staticmethod
    def ensure_not_banned(user: User) -> None:
        if user.is_banned:
            raise UserBannedError()

    # ------------------------------------------------------------------
    # Flagging & escalation
    # ------------------------------------------------------------------
    async def flag(
        self,
        user_id: int | None,
        *,
        rule: str,
        severity: int = 1,
        description: str | None = None,
        meta: dict | None = None,
    ) -> None:
        await self.repo.flag(
            user_id=user_id,
            rule=rule,
            severity=severity,
            description=description,
            meta=meta,
        )
        if user_id is not None:
            await self.session.execute(
                update(User)
                .where(User.id == user_id)
                .values(suspicion_score=User.suspicion_score + severity)
            )

    # ------------------------------------------------------------------
    # Duplicate / referral-farm heuristics
    # ------------------------------------------------------------------
    async def detect_referral_farm(self, referrer_id: int) -> bool:
        """Flag suspicious bursts of referrals from a single referrer.

        Many accounts referred within a short window is a classic abuse pattern.
        """
        window_start = datetime.now(UTC) - timedelta(hours=1)
        result = await self.session.execute(
            select(func.count())
            .select_from(User)
            .where(User.referrer_id == referrer_id, User.created_at >= window_start)
        )
        recent = int(result.scalar_one())
        if recent >= 10:
            await self.flag(
                referrer_id,
                rule="referral_farm",
                severity=10,
                description=f"{recent} referrals within 1 hour.",
            )
            return True
        return False

    async def is_high_risk(self, user: User) -> bool:
        return user.suspicion_score >= SUSPICION_HARD_LIMIT
