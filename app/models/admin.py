"""Administration and anti-cheat audit models."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class AdminLog(Base, IntPKMixin):
    """Audit trail of every privileged admin action."""

    __tablename__ = "admin_logs"

    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(48), nullable=False)
    target_user_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_admin_logs_action_created", "action", "created_at"),)


class AntiCheatLog(Base, IntPKMixin):
    """Records suspicious activity flagged by the anti-cheat system."""

    __tablename__ = "anti_cheat_logs"

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    rule: Mapped[str] = mapped_column(String(48), nullable=False)
    severity: Mapped[int] = mapped_column(BigInteger, default=1, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User | None] = relationship()

    __table_args__ = (Index("ix_anti_cheat_rule_created", "rule", "created_at"),)
