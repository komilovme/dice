"""Repository for inventory items, powerups and case openings."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.config.constants import CaseRarity, PowerupType, RewardKind
from app.models.inventory import CaseOpening, InventoryItem, UserPowerup
from app.repositories.base import BaseRepository


class InventoryRepository(BaseRepository[InventoryItem]):
    model = InventoryItem

    async def list_for_user(self, user_id: int) -> list[InventoryItem]:
        result = await self.session.execute(
            select(InventoryItem).where(InventoryItem.user_id == user_id)
        )
        return list(result.scalars().all())

    async def grant_item(
        self,
        *,
        user_id: int,
        kind: RewardKind,
        item_code: str,
        label: str | None,
        quantity: int = 1,
    ) -> None:
        """Idempotent upsert: increments quantity if the item already exists."""
        stmt = (
            pg_insert(InventoryItem)
            .values(
                user_id=user_id,
                kind=kind,
                item_code=item_code,
                label=label,
                quantity=quantity,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "kind", "item_code"],
                set_={"quantity": InventoryItem.quantity + quantity},
            )
        )
        await self.session.execute(stmt)


class PowerupRepository(BaseRepository[UserPowerup]):
    model = UserPowerup

    async def get(self, user_id: int, ptype: PowerupType) -> UserPowerup | None:  # type: ignore[override]
        result = await self.session.execute(
            select(UserPowerup).where(UserPowerup.user_id == user_id, UserPowerup.type == ptype)
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[UserPowerup]:
        result = await self.session.execute(
            select(UserPowerup).where(UserPowerup.user_id == user_id)
        )
        return list(result.scalars().all())

    async def grant(
        self,
        *,
        user_id: int,
        ptype: PowerupType,
        charges: int = 1,
        expires_at: datetime | None = None,
    ) -> None:
        stmt = (
            pg_insert(UserPowerup)
            .values(
                user_id=user_id,
                type=ptype,
                charges=charges,
                expires_at=expires_at,
            )
            .on_conflict_do_update(
                index_elements=["user_id", "type"],
                set_={"charges": UserPowerup.charges + charges},
            )
        )
        await self.session.execute(stmt)

    async def consume_charge(self, powerup_id: int) -> None:
        await self.session.execute(
            update(UserPowerup)
            .where(UserPowerup.id == powerup_id, UserPowerup.charges > 0)
            .values(charges=UserPowerup.charges - 1)
        )


class CaseOpeningRepository(BaseRepository[CaseOpening]):
    model = CaseOpening

    async def record(
        self,
        *,
        user_id: int,
        case_code: str,
        rarity: CaseRarity,
        price: int,
        reward_kind: RewardKind,
        reward_coins: int,
        reward_item_code: str | None,
        reward_label: str | None,
    ) -> CaseOpening:
        opening = CaseOpening(
            user_id=user_id,
            case_code=case_code,
            rarity=rarity,
            price=price,
            reward_kind=reward_kind,
            reward_coins=reward_coins,
            reward_item_code=reward_item_code,
            reward_label=reward_label,
        )
        self.session.add(opening)
        await self.session.flush()
        return opening
