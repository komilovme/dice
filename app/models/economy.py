"""Economy models: transaction ledger and reward claim history."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import TransactionType
from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class Transaction(Base, IntPKMixin):
    """Append-only ledger entry for every coin movement.

    ``amount`` is signed (positive = credit, negative = debit). ``balance_after``
    snapshots the user's balance for auditability and dispute resolution.
    """

    __tablename__ = "transactions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type: Mapped[TransactionType] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    # Optional reference to a related entity (battle id, case opening id, ...).
    reference: Mapped[str | None] = mapped_column(String(64), index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="transactions")

    __table_args__ = (
        Index("ix_transactions_user_created", "user_id", "created_at"),
        Index("ix_transactions_type_created", "type", "created_at"),
    )


class RewardClaim(Base, IntPKMixin):
    """Records each claimed periodic reward (daily / weekly / lucky chest).

    Used both for analytics and to enforce idempotent claiming windows.
    """

    __tablename__ = "reward_claims"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    reward_type: Mapped[TransactionType] = mapped_column(String(32), nullable=False)
    amount: Mapped[int] = mapped_column(BigInteger, nullable=False)
    streak_day: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="reward_claims")

    __table_args__ = (Index("ix_reward_claims_user_type", "user_id", "reward_type", "created_at"),)
