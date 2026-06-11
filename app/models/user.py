"""User and per-user aggregate statistics models."""

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
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config.constants import Rank
from app.database.base import Base, IntPKMixin, TimestampMixin

if TYPE_CHECKING:
    from app.models.clan import ClanMember
    from app.models.economy import RewardClaim, Transaction
    from app.models.inventory import CaseOpening, InventoryItem, UserPowerup
    from app.models.user_achievement import UserAchievement


class User(Base, IntPKMixin, TimestampMixin):
    """A Telegram user playing the bot.

    ``id`` is the internal surrogate key; ``telegram_id`` is the external
    Telegram identifier used for lookups from updates.
    """

    __tablename__ = "users"

    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(64), index=True)
    first_name: Mapped[str | None] = mapped_column(String(128))
    last_name: Mapped[str | None] = mapped_column(String(128))
    language_code: Mapped[str | None] = mapped_column(String(8))

    # Economy
    balance: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    # Progression
    xp: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    rank: Mapped[Rank] = mapped_column(String(16), default=Rank.BRONZE, nullable=False)
    current_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    best_streak: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Cosmetics (equipped item codes; ownership tracked in inventory_items)
    active_title: Mapped[str | None] = mapped_column(String(64))
    active_frame: Mapped[str | None] = mapped_column(String(64))

    # Referral system
    referrer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    referral_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Moderation / anti-cheat
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[str | None] = mapped_column(Text)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    suspicion_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Activity timestamps
    last_daily_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_weekly_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_chest_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # ----- Relationships -----
    stats: Mapped[UserStats] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    referrer: Mapped[User | None] = relationship(remote_side="User.id", backref="referrals")
    transactions: Mapped[list[Transaction]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    reward_claims: Mapped[list[RewardClaim]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    achievements: Mapped[list[UserAchievement]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    powerups: Mapped[list[UserPowerup]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    inventory_items: Mapped[list[InventoryItem]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    case_openings: Mapped[list[CaseOpening]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    clan_membership: Mapped[ClanMember | None] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_balance_desc", balance.desc()),
        Index("ix_users_xp_desc", xp.desc()),
    )

    @property
    def display_name(self) -> str:
        if self.username:
            return f"@{self.username}"
        name = " ".join(filter(None, [self.first_name, self.last_name]))
        return name or f"Player {self.telegram_id}"

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} tg={self.telegram_id} bal={self.balance}>"


class UserStats(Base, TimestampMixin):
    """One-to-one aggregate statistics for a user.

    Kept in a separate table so high-frequency stat updates do not contend with
    the wider ``users`` row (and to keep leaderboard queries focused).
    """

    __tablename__ = "user_stats"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    total_games: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    wins: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    losses: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    draws: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    biggest_win: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    biggest_loss: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    total_wagered: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    coins_earned: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    coins_spent: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)

    tournaments_won: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    user: Mapped[User] = relationship(back_populates="stats")

    @property
    def win_rate(self) -> float:
        """Win rate as a fraction in [0, 1]. Draws excluded from denominator."""
        decisive = self.wins + self.losses
        if decisive == 0:
            return 0.0
        return self.wins / decisive

    @property
    def win_rate_pct(self) -> float:
        return round(self.win_rate * 100, 2)
