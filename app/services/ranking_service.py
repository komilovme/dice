"""Ranking & XP progression service.

Ranks are derived from XP (primary) gated by a wins requirement so a player must
actually play to climb. XP is awarded per battle outcome with a small bonus that
scales with the pot size.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import update

from app.config.constants import (
    RANK_TIERS,
    XP_PER_DRAW,
    XP_PER_LOSS,
    XP_PER_WIN,
    XP_POT_DIVISOR,
    Rank,
    RankTier,
)
from app.models.user import User
from app.services.base import BaseService


@dataclass(slots=True)
class XPResult:
    xp_gained: int
    new_xp: int
    old_rank: Rank
    new_rank: Rank
    promoted: bool


def rank_for(xp: int, wins: int) -> RankTier:
    """Return the highest rank tier the player qualifies for."""
    current = RANK_TIERS[0]
    for tier in RANK_TIERS:
        if xp >= tier.min_xp and wins >= tier.min_wins:
            current = tier
        else:
            break
    return current


def next_tier(current: Rank) -> RankTier | None:
    """Return the tier immediately above ``current`` (or None at the top)."""
    for index, tier in enumerate(RANK_TIERS):
        if tier.rank == current and index + 1 < len(RANK_TIERS):
            return RANK_TIERS[index + 1]
    return None


def xp_for_outcome(*, won: bool, draw: bool, pot: int, multiplier: float = 1.0) -> int:
    """Compute XP for a single battle outcome."""
    if draw:
        base = XP_PER_DRAW
    elif won:
        base = XP_PER_WIN + pot // XP_POT_DIVISOR
    else:
        base = XP_PER_LOSS
    return int(base * multiplier)


class RankingService(BaseService):
    async def award_xp(self, user: User, xp_gained: int) -> XPResult:
        """Add XP to a user and recompute their rank, persisting both."""
        old_rank = Rank(user.rank)
        new_xp = user.xp + xp_gained
        wins = user.stats.wins if user.stats else 0
        new_tier = rank_for(new_xp, wins)

        await self.session.execute(
            update(User).where(User.id == user.id).values(xp=new_xp, rank=new_tier.rank)
        )
        # Keep the in-memory object consistent for callers.
        user.xp = new_xp
        user.rank = new_tier.rank

        return XPResult(
            xp_gained=xp_gained,
            new_xp=new_xp,
            old_rank=old_rank,
            new_rank=new_tier.rank,
            promoted=new_tier.rank != old_rank,
        )

    @staticmethod
    def progress_to_next(user: User) -> tuple[int, int]:
        """Return (xp_into_current_band, xp_needed_for_next) for a progress bar."""
        tier = next_tier(Rank(user.rank))
        if tier is None:
            return (1, 1)  # max rank
        current_tier = rank_for(user.xp, user.stats.wins if user.stats else 0)
        span = tier.min_xp - current_tier.min_xp
        into = user.xp - current_tier.min_xp
        return (max(0, into), max(1, span))
