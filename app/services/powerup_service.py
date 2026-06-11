"""Powerup shop & inventory service."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.config.constants import POWERUPS, PowerupType, TransactionType
from app.models.inventory import UserPowerup
from app.models.user import User
from app.repositories.inventory_repository import PowerupRepository
from app.services.base import BaseService
from app.services.economy_service import EconomyService
from app.utils.exceptions import NotFoundError


class PowerupService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = PowerupRepository(session)
        self.economy = EconomyService(session, redis)

    async def buy(self, *, user: User, ptype: PowerupType) -> UserPowerup:
        definition = POWERUPS.get(ptype)
        if definition is None:
            raise NotFoundError("Unknown powerup.")
        await self.economy.debit(
            user.id,
            definition.price,
            type=TransactionType.POWERUP_PURCHASE,
            description=f"Bought {definition.name}",
            reference=ptype,
        )
        expires = (
            datetime.now(UTC) + timedelta(seconds=definition.duration_seconds)
            if definition.duration_seconds
            else None
        )
        await self.repo.grant(user_id=user.id, ptype=ptype, charges=1, expires_at=expires)
        powerup = await self.repo.get(user.id, ptype)
        assert powerup is not None
        return powerup

    async def inventory(self, user: User) -> list[UserPowerup]:
        return await self.repo.list_for_user(user.id)
