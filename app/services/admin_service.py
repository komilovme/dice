"""Administration service: privileged operations with full audit logging.

Every action writes an :class:`AdminLog` entry so privileged changes are
traceable. Coin grants/removals flow through the economy ledger like any other
transaction for consistency.
"""

from __future__ import annotations

from typing import Any

from app.config.constants import TransactionType
from app.models.user import User
from app.repositories.admin_repository import AdminLogRepository, AntiCheatRepository
from app.repositories.user_repository import UserRepository
from app.services.base import BaseService
from app.services.economy_service import EconomyService
from app.services.season_service import SeasonService
from app.utils.exceptions import NotFoundError, ValidationError


class AdminService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.users = UserRepository(session)
        self.logs = AdminLogRepository(session)
        self.anticheat = AntiCheatRepository(session)
        self.economy = EconomyService(session, redis)

    async def _resolve_target(self, target_telegram_id: int) -> User:
        user = await self.users.get_by_telegram_id(target_telegram_id)
        if user is None:
            raise NotFoundError("Target user not found.")
        return user

    async def give_coins(self, *, admin_id: int, target_telegram_id: int, amount: int) -> int:
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        target = await self._resolve_target(target_telegram_id)
        new_balance = await self.economy.credit(
            target.id,
            amount,
            type=TransactionType.ADMIN_GRANT,
            description=f"Admin grant by {admin_id}",
            track_stats=False,
        )
        await self.logs.record(
            admin_id=admin_id,
            action="give_coins",
            target_user_id=target_telegram_id,
            details={"amount": amount, "new_balance": new_balance},
        )
        return new_balance

    async def remove_coins(self, *, admin_id: int, target_telegram_id: int, amount: int) -> int:
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        target = await self._resolve_target(target_telegram_id)
        # Clamp so we never drive a balance negative.
        amount = min(amount, target.balance)
        new_balance = target.balance
        if amount:
            new_balance = await self.economy.debit(
                target.id,
                amount,
                type=TransactionType.ADMIN_REMOVE,
                description=f"Admin removal by {admin_id}",
                track_stats=False,
            )
        await self.logs.record(
            admin_id=admin_id,
            action="remove_coins",
            target_user_id=target_telegram_id,
            details={"amount": amount, "new_balance": new_balance},
        )
        return new_balance

    async def ban_user(self, *, admin_id: int, target_telegram_id: int, reason: str | None) -> None:
        target = await self._resolve_target(target_telegram_id)
        await self.users.set_banned(target.id, banned=True, reason=reason)
        await self.logs.record(
            admin_id=admin_id,
            action="ban_user",
            target_user_id=target_telegram_id,
            details={"reason": reason},
        )

    async def unban_user(self, *, admin_id: int, target_telegram_id: int) -> None:
        target = await self._resolve_target(target_telegram_id)
        await self.users.set_banned(target.id, banned=False, reason=None)
        await self.logs.record(
            admin_id=admin_id,
            action="unban_user",
            target_user_id=target_telegram_id,
        )

    async def recent_logs(self, limit: int = 20):
        return await self.logs.recent(limit)

    async def recent_anticheat(self, limit: int = 20):
        return await self.anticheat.recent(limit)

    async def force_season_reset(self, *, admin_id: int):
        result = await SeasonService(self.session, self.redis).rollover()
        await self.logs.record(
            admin_id=admin_id,
            action="force_season_reset",
            details={
                "finalized": result.finalized_season.number if result.finalized_season else None,
                "new_season": result.new_season.number,
                "rewarded": result.rewarded_players,
            },
        )
        return result

    async def create_event(self, *, admin_id: int, name: str, payload: dict[str, Any]) -> None:
        """Record an event/announcement. Stored in Redis for the scheduler/bot
        to broadcast, plus an audit log entry."""
        if self.redis is not None:
            import orjson

            await self.redis.set(
                f"event:{name}", orjson.dumps(payload), ex=payload.get("ttl", 86_400)
            )
        await self.logs.record(
            admin_id=admin_id,
            action="create_event",
            details={"name": name, **payload},
        )
