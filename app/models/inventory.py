"""Inventory models: owned cosmetic items, powerups, and case opening history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import CaseRarity, PowerupType, RewardKind
from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class InventoryItem(Base, IntPKMixin):
    """A cosmetic item (title / frame / badge) owned by a user."""

    __tablename__ = "inventory_items"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    kind: Mapped[RewardKind] = mapped_column(String(16), nullable=False)
    item_code: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str | None] = mapped_column(String(128))
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="inventory_items")

    __table_args__ = (Index("uq_inventory_item", "user_id", "kind", "item_code", unique=True),)


class UserPowerup(Base, IntPKMixin):
    """A powerup owned by a user. Charges deplete on use; time-based powerups
    use ``expires_at`` to mark when their effect ends."""

    __tablename__ = "user_powerups"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[PowerupType] = mapped_column(String(24), nullable=False)
    charges: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="powerups")

    __table_args__ = (Index("uq_user_powerup", "user_id", "type", unique=True),)


class CaseOpening(Base, IntPKMixin):
    """Audit record of a paid case opening and its resulting reward."""

    __tablename__ = "case_openings"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    case_code: Mapped[str] = mapped_column(String(32), nullable=False)
    rarity: Mapped[CaseRarity] = mapped_column(String(16), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)

    reward_kind: Mapped[RewardKind] = mapped_column(String(16), nullable=False)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    reward_item_code: Mapped[str | None] = mapped_column(String(64))
    reward_label: Mapped[str | None] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="case_openings")

    __table_args__ = (Index("ix_case_openings_user_created", "user_id", "created_at"),)
