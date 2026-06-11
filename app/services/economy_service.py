"""Virtual economy service: balances, ledger, and periodic rewards.

All coin movements flow through :meth:`credit` / :meth:`debit` so that every
change is recorded in the append-only transaction ledger with a balance
snapshot. Balance mutations use atomic, guarded SQL updates to remain correct
under high concurrency.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import update

from app.config.constants import (
    LUCKY_CHEST_COOLDOWN_HOURS,
    LUCKY_CHEST_REWARDS,
    TransactionType,
)
from app.config.settings import settings
from app.models.user import User, UserStats
from app.repositories.economy_repository import (
    RewardClaimRepository,
    TransactionRepository,
)
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.utils.exceptions import InsufficientBalanceError, RewardNotReadyError

DAILY_COOLDOWN = timedelta(hours=24)
DAILY_STREAK_WINDOW = timedelta(hours=48)
WEEKLY_COOLDOWN = timedelta(days=7)
DAILY_STREAK_BONUS = 50  # per consecutive day, capped
DAILY_STREAK_CAP = 7


@dataclass(slots=True)
class RewardResult:
    amount: int
    new_balance: int
    streak_day: int = 0


class EconomyService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.users = UserRepository(session)
        self.transactions = TransactionRepository(session)
        self.claims = RewardClaimRepository(session)

    # ------------------------------------------------------------------
    # Core balance operations
    # ------------------------------------------------------------------
    async def credit(
        self,
        user_id: int,
        amount: int,
        *,
        type: TransactionType,
        description: str | None = None,
        reference: str | None = None,
        track_stats: bool = True,
    ) -> int:
        """Add coins to a user and record a ledger entry. Returns new balance."""
        if amount < 0:
            raise ValueError("credit amount must be non-negative")
        new_balance = await self.users.adjust_balance(user_id, amount)
        await self.transactions.record(
            user_id=user_id,
            type=type,
            amount=amount,
            balance_after=new_balance,
            description=description,
            reference=reference,
        )
        if track_stats and amount:
            await self.session.execute(
                update(UserStats)
                .where(UserStats.user_id == user_id)
                .values(coins_earned=UserStats.coins_earned + amount)
            )
        return new_balance

    async def debit(
        self,
        user_id: int,
        amount: int,
        *,
        type: TransactionType,
        description: str | None = None,
        reference: str | None = None,
        track_stats: bool = True,
    ) -> int:
        """Remove coins if affordable, else raise InsufficientBalanceError."""
        if amount < 0:
            raise ValueError("debit amount must be non-negative")
        new_balance = await self.users.try_debit(user_id, amount)
        if new_balance is None:
            user = await self.users.get(user_id)
            raise InsufficientBalanceError(amount, user.balance if user else 0)
        await self.transactions.record(
            user_id=user_id,
            type=type,
            amount=-amount,
            balance_after=new_balance,
            description=description,
            reference=reference,
        )
        if track_stats and amount:
            await self.session.execute(
                update(UserStats)
                .where(UserStats.user_id == user_id)
                .values(coins_spent=UserStats.coins_spent + amount)
            )
        return new_balance

    async def grant_signup_bonus(self, user_id: int) -> int:
        # Starting balance is set on the user row at creation; we only log it.
        await self.transactions.record(
            user_id=user_id,
            type=TransactionType.SIGNUP_BONUS,
            amount=settings.starting_balance,
            balance_after=settings.starting_balance,
            description="Welcome bonus",
        )
        return settings.starting_balance

    # ------------------------------------------------------------------
    # Periodic rewards
    # ------------------------------------------------------------------
    async def claim_daily(self, user: User) -> RewardResult:
        now = datetime.now(UTC)
        last = user.last_daily_at
        if last is not None:
            elapsed = now - last
            if elapsed < DAILY_COOLDOWN:
                raise RewardNotReadyError(int((DAILY_COOLDOWN - elapsed).total_seconds()), "daily")

        # Determine streak: consecutive if claimed within the streak window.
        last_claim = await self.claims.last_claim(user.id, TransactionType.DAILY_REWARD)
        streak_day = 1
        if last_claim is not None and (now - last_claim.created_at) <= DAILY_STREAK_WINDOW:
            streak_day = last_claim.streak_day + 1

        bonus = min(streak_day, DAILY_STREAK_CAP) * DAILY_STREAK_BONUS
        amount = settings.daily_reward + bonus

        new_balance = await self.credit(
            user.id,
            amount,
            type=TransactionType.DAILY_REWARD,
            description=f"Daily reward (day {streak_day})",
        )
        await self.claims.record(
            user_id=user.id,
            reward_type=TransactionType.DAILY_REWARD,
            amount=amount,
            streak_day=streak_day,
        )
        await self.session.execute(update(User).where(User.id == user.id).values(last_daily_at=now))
        return RewardResult(amount=amount, new_balance=new_balance, streak_day=streak_day)

    async def claim_weekly(self, user: User) -> RewardResult:
        now = datetime.now(UTC)
        last = user.last_weekly_at
        if last is not None:
            elapsed = now - last
            if elapsed < WEEKLY_COOLDOWN:
                raise RewardNotReadyError(
                    int((WEEKLY_COOLDOWN - elapsed).total_seconds()), "weekly"
                )
        amount = settings.weekly_reward
        new_balance = await self.credit(
            user.id, amount, type=TransactionType.WEEKLY_REWARD, description="Weekly reward"
        )
        await self.claims.record(
            user_id=user.id, reward_type=TransactionType.WEEKLY_REWARD, amount=amount
        )
        await self.session.execute(
            update(User).where(User.id == user.id).values(last_weekly_at=now)
        )
        return RewardResult(amount=amount, new_balance=new_balance)

    async def open_lucky_chest(self, user: User) -> RewardResult:
        now = datetime.now(UTC)
        cooldown = timedelta(hours=LUCKY_CHEST_COOLDOWN_HOURS)
        if user.last_chest_at is not None:
            elapsed = now - user.last_chest_at
            if elapsed < cooldown:
                raise RewardNotReadyError(int((cooldown - elapsed).total_seconds()), "lucky chest")
        amount = self._weighted_chest_reward()
        new_balance = await self.credit(
            user.id, amount, type=TransactionType.CHEST_REWARD, description="Lucky chest"
        )
        await self.claims.record(
            user_id=user.id, reward_type=TransactionType.CHEST_REWARD, amount=amount
        )
        await self.session.execute(update(User).where(User.id == user.id).values(last_chest_at=now))
        return RewardResult(amount=amount, new_balance=new_balance)

    @staticmethod
    def _weighted_chest_reward() -> int:
        total = sum(weight for _, weight in LUCKY_CHEST_REWARDS)
        pick = secrets.SystemRandom().uniform(0, total)
        cumulative = 0.0
        for coins, weight in LUCKY_CHEST_REWARDS:
            cumulative += weight
            if pick <= cumulative:
                return coins
        return LUCKY_CHEST_REWARDS[0][0]

    async def history(self, user_id: int, *, limit: int = 15):
        return await self.transactions.history(user_id, limit=limit)
