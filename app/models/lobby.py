"""Lobby and lobby-member models for matchmaking."""

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

from app.config.constants import BattleMode, LobbyStatus
from app.database.base import Base, IntPKMixin

if TYPE_CHECKING:
    from app.models.user import User


class Lobby(Base, IntPKMixin):
    """A pre-battle lobby where players gather before a match starts."""

    __tablename__ = "lobbies"

    code: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(64))
    mode: Mapped[BattleMode] = mapped_column(String(16), nullable=False)
    status: Mapped[LobbyStatus] = mapped_column(
        String(16), default=LobbyStatus.OPEN, nullable=False, index=True
    )

    host_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    stake: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    max_players: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    min_players: Mapped[int] = mapped_column(Integer, default=2, nullable=False)

    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Hashed password for private lobbies (never store plaintext).
    password_hash: Mapped[str | None] = mapped_column(String(128))

    chat_id: Mapped[int | None] = mapped_column(BigInteger, index=True)
    battle_id: Mapped[int | None] = mapped_column(ForeignKey("battles.id", ondelete="SET NULL"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    host: Mapped[User] = relationship(foreign_keys=[host_id])
    members: Mapped[list[LobbyMember]] = relationship(
        back_populates="lobby",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="LobbyMember.id",
    )

    __table_args__ = (
        Index("ix_lobbies_status_private", "status", "is_private"),
        Index("ix_lobbies_mode_stake", "mode", "stake"),
    )

    @property
    def is_full(self) -> bool:
        return len(self.members) >= self.max_players


class LobbyMember(Base, IntPKMixin):
    """Membership of a user in a lobby."""

    __tablename__ = "lobby_members"

    lobby_id: Mapped[int] = mapped_column(
        ForeignKey("lobbies.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    team: Mapped[int | None] = mapped_column(Integer)
    is_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lobby: Mapped[Lobby] = relationship(back_populates="members")
    user: Mapped[User] = relationship()

    __table_args__ = (Index("uq_lobby_member", "lobby_id", "user_id", unique=True),)
