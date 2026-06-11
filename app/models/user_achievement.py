"""User achievement unlock records.

The achievement *catalogue* lives in ``app.config.constants.ACHIEVEMENTS``;
this table only records which achievements a user has unlocked and when.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class UserAchievement(Base, IntPKMixin):
    __tablename__ = "user_achievements"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code: Mapped[str] = mapped_column(String(48), nullable=False)
    unlocked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="achievements")

    __table_args__ = (Index("uq_user_achievement", "user_id", "code", unique=True),)
