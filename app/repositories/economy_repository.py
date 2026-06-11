"""Repositories for the transaction ledger and reward claims."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import desc, select

from app.config.constants import TransactionType
from app.models.economy import RewardClaim, Transaction
from app.repositories.base import BaseRepository


class TransactionRepository(BaseRepository[Transaction]):
    model = Transaction

    async def record(
        self,
        *,
        user_id: int,
        type: TransactionType,
        amount: int,
        balance_after: int,
        description: str | None = None,
        reference: str | None = None,
    ) -> Transaction:
        txn = Transaction(
            user_id=user_id,
            type=type,
            amount=amount,
            balance_after=balance_after,
            description=description,
            reference=reference,
        )
        self.session.add(txn)
        await self.session.flush()
        return txn

    async def history(self, user_id: int, *, limit: int = 20, offset: int = 0) -> list[Transaction]:
        result = await self.session.execute(
            select(Transaction)
            .where(Transaction.user_id == user_id)
            .order_by(desc(Transaction.created_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())


class RewardClaimRepository(BaseRepository[RewardClaim]):
    model = RewardClaim

    async def record(
        self,
        *,
        user_id: int,
        reward_type: TransactionType,
        amount: int,
        streak_day: int = 0,
    ) -> RewardClaim:
        claim = RewardClaim(
            user_id=user_id,
            reward_type=reward_type,
            amount=amount,
            streak_day=streak_day,
        )
        self.session.add(claim)
        await self.session.flush()
        return claim

    async def last_claim(self, user_id: int, reward_type: TransactionType) -> RewardClaim | None:
        result = await self.session.execute(
            select(RewardClaim)
            .where(
                RewardClaim.user_id == user_id,
                RewardClaim.reward_type == reward_type,
            )
            .order_by(desc(RewardClaim.created_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def count_since(self, user_id: int, reward_type: TransactionType, since: datetime) -> int:
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count())
            .select_from(RewardClaim)
            .where(
                RewardClaim.user_id == user_id,
                RewardClaim.reward_type == reward_type,
                RewardClaim.created_at >= since,
            )
        )
        return int(result.scalar_one())
