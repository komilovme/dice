"""Repository for users and their aggregate statistics."""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from app.models.user import User, UserStats
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.telegram_id == telegram_id).options(selectinload(User.stats))
        )
        return result.scalar_one_or_none()

    async def get_with_stats(self, user_id: int) -> User | None:
        result = await self.session.execute(
            select(User).where(User.id == user_id).options(selectinload(User.stats))
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        telegram_id: int,
        username: str | None,
        first_name: str | None,
        last_name: str | None,
        language_code: str | None,
        starting_balance: int,
        referrer_id: int | None = None,
        is_admin: bool = False,
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            balance=starting_balance,
            referrer_id=referrer_id,
            is_admin=is_admin,
            stats=UserStats(),
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def adjust_balance(self, user_id: int, delta: int) -> int:
        """Atomically adjust a balance at the DB level and return the new value.

        Uses a single UPDATE ... RETURNING to avoid read-modify-write races
        under concurrency.
        """
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(balance=User.balance + delta)
            .returning(User.balance)
        )
        return int(result.scalar_one())

    async def try_debit(self, user_id: int, amount: int) -> int | None:
        """Atomically debit ``amount`` only if the balance is sufficient.

        Returns the new balance, or ``None`` if the balance was too low. The
        ``WHERE balance >= amount`` guard makes this safe without locking.
        """
        result = await self.session.execute(
            update(User)
            .where(User.id == user_id, User.balance >= amount)
            .values(balance=User.balance - amount)
            .returning(User.balance)
        )
        new_balance = result.scalar_one_or_none()
        return int(new_balance) if new_balance is not None else None

    async def update_last_seen(self, telegram_id: int) -> None:
        from sqlalchemy import func

        await self.session.execute(
            update(User).where(User.telegram_id == telegram_id).values(last_seen_at=func.now())
        )

    async def set_banned(self, user_id: int, *, banned: bool, reason: str | None) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(is_banned=banned, ban_reason=reason)
        )

    async def increment_referrals(self, user_id: int) -> None:
        await self.session.execute(
            update(User).where(User.id == user_id).values(referral_count=User.referral_count + 1)
        )
