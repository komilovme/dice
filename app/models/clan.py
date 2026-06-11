"""Clan system models: clans, members, and clan wars."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import ClanRole
from app.database.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class Clan(Base, IntPKMixin, TimestampMixin):
    """A player-created clan with a shared treasury and ranking."""

    __tablename__ = "clans"

    name: Mapped[str] = mapped_column(String(48), unique=True, index=True, nullable=False)
    tag: Mapped[str] = mapped_column(String(8), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    emblem: Mapped[str | None] = mapped_column(String(16), default="🛡")

    leader_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    treasury: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_points: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    wars_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_members: Mapped[int] = mapped_column(Integer, default=25, nullable=False)

    members: Mapped[list[ClanMember]] = relationship(
        back_populates="clan",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    leader: Mapped[User] = relationship(foreign_keys=[leader_id])

    __table_args__ = (Index("ix_clans_points_desc", total_points.desc()),)

    @property
    def member_count(self) -> int:
        return len(self.members)


class ClanMember(Base, IntPKMixin):
    """A user's membership and role within a clan (one clan per user)."""

    __tablename__ = "clan_members"

    clan_id: Mapped[int] = mapped_column(ForeignKey("clans.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    role: Mapped[ClanRole] = mapped_column(String(16), default=ClanRole.MEMBER, nullable=False)
    contributed: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    clan: Mapped[Clan] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="clan_membership")

    __table_args__ = (Index("ix_clan_members_clan_role", "clan_id", "role"),)


class ClanWar(Base, IntPKMixin):
    """A scheduled head-to-head competition between two clans."""

    __tablename__ = "clan_wars"

    clan_a_id: Mapped[int] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    clan_b_id: Mapped[int] = mapped_column(
        ForeignKey("clans.id", ondelete="CASCADE"), nullable=False
    )
    clan_a_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    clan_b_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    prize_pool: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    winner_clan_id: Mapped[int | None] = mapped_column(ForeignKey("clans.id", ondelete="SET NULL"))

    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    clan_a: Mapped[Clan] = relationship(foreign_keys=[clan_a_id])
    clan_b: Mapped[Clan] = relationship(foreign_keys=[clan_b_id])
