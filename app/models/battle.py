"""Battle and battle-participant models covering all game modes."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import BattleMode, BattleStatus
from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.season import Season
    from app.models.user import User


class Battle(Base, IntPKMixin):
    """A single dice battle instance across any supported mode."""

    __tablename__ = "battles"

    mode: Mapped[BattleMode] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[BattleStatus] = mapped_column(
        String(16), default=BattleStatus.PENDING, nullable=False, index=True
    )

    stake: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    pot: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    house_cut: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    is_team_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    winner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    winning_team: Mapped[int | None] = mapped_column(Integer)

    season_id: Mapped[int | None] = mapped_column(
        ForeignKey("seasons.id", ondelete="SET NULL"), index=True
    )

    # Telegram context for group-mode cleanup and result posting.
    chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int | None] = mapped_column(BigInteger)

    extra: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    participants: Mapped[list[BattleParticipant]] = relationship(
        back_populates="battle",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="BattleParticipant.id",
    )
    winner: Mapped[User | None] = relationship(foreign_keys=[winner_id])
    season: Mapped[Season | None] = relationship()

    __table_args__ = (
        Index("ix_battles_mode_status", "mode", "status"),
        Index("ix_battles_chat_status", "chat_id", "status"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Battle id={self.id} mode={self.mode} status={self.status}>"


class BattleParticipant(Base, IntPKMixin):
    """A user's participation and result within a battle."""

    __tablename__ = "battle_participants"

    battle_id: Mapped[int] = mapped_column(
        ForeignKey("battles.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    team: Mapped[int | None] = mapped_column(Integer)
    # Final score used to determine the winner (sum of dice rolls).
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Individual dice values for transparency / replay.
    rolls: Mapped[list[int]] = mapped_column(JSONB, default=list, nullable=False)
    has_rolled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_winner: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    payout: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    # Snapshot of powerups applied to this participant for this battle.
    powerups_used: Mapped[list[str]] = mapped_column(JSONB, default=list, nullable=False)

    battle: Mapped[Battle] = relationship(back_populates="participants")
    user: Mapped[User] = relationship()

    __table_args__ = (
        Index("uq_battle_participant", "battle_id", "user_id", unique=True),
        Index("ix_battle_participants_user", "user_id"),
    )
