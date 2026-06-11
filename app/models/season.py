"""Seasonal system models: seasons, per-season participation, and hall of fame."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class Season(Base, IntPKMixin):
    """A monthly competitive season."""

    __tablename__ = "seasons"

    name: Mapped[str] = mapped_column(String(64), nullable=False)
    number: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    participants: Mapped[list[SeasonParticipant]] = relationship(
        back_populates="season", cascade="all, delete-orphan"
    )


class SeasonParticipant(Base, IntPKMixin):
    """A user's score within a specific season (reset each season)."""

    __tablename__ = "season_participants"

    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    season_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    season_wins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    season_coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    final_rank: Mapped[int | None] = mapped_column(Integer)

    season: Mapped[Season] = relationship(back_populates="participants")
    user: Mapped[User] = relationship()

    __table_args__ = (
        Index("uq_season_participant", "season_id", "user_id", unique=True),
        Index("ix_season_participants_points", "season_id", season_points.desc()),
    )


class HallOfFame(Base, IntPKMixin):
    """Permanent record of season winners and the badges they earned."""

    __tablename__ = "hall_of_fame"

    season_id: Mapped[int] = mapped_column(
        ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    placement: Mapped[int] = mapped_column(Integer, nullable=False)
    season_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    badge_code: Mapped[str | None] = mapped_column(String(64))
    reward_coins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    season: Mapped[Season] = relationship()
    user: Mapped[User] = relationship()

    __table_args__ = (Index("ix_hall_of_fame_season_placement", "season_id", "placement"),)
