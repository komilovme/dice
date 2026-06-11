"""Read-optimised queries powering global, group and season leaderboards."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Float, cast, desc, func, select

from app.models.season import SeasonParticipant
from app.models.user import User, UserStats
from app.repositories.base import BaseRepository

# Minimum decisive games before a player qualifies for the win-rate board,
# preventing a 1-win-0-loss player from topping the chart.
MIN_GAMES_FOR_WINRATE = 20


@dataclass(slots=True)
class LeaderboardEntry:
    rank: int
    user_id: int
    telegram_id: int
    display_name: str
    value: float


class LeaderboardRepository(BaseRepository[User]):
    model = User

    async def _rows_to_entries(self, rows) -> list[LeaderboardEntry]:
        entries: list[LeaderboardEntry] = []
        for position, (user, value) in enumerate(rows, start=1):
            entries.append(
                LeaderboardEntry(
                    rank=position,
                    user_id=user.id,
                    telegram_id=user.telegram_id,
                    display_name=user.display_name,
                    value=float(value),
                )
            )
        return entries

    async def richest(self, limit: int = 10) -> list[LeaderboardEntry]:
        result = await self.session.execute(
            select(User, User.balance)
            .where(User.is_banned.is_(False))
            .order_by(desc(User.balance))
            .limit(limit)
        )
        return await self._rows_to_entries(result.all())

    async def most_wins(self, limit: int = 10) -> list[LeaderboardEntry]:
        result = await self.session.execute(
            select(User, UserStats.wins)
            .join(UserStats, UserStats.user_id == User.id)
            .where(User.is_banned.is_(False))
            .order_by(desc(UserStats.wins))
            .limit(limit)
        )
        return await self._rows_to_entries(result.all())

    async def highest_win_rate(self, limit: int = 10) -> list[LeaderboardEntry]:
        decisive = UserStats.wins + UserStats.losses
        win_rate = cast(UserStats.wins, Float) / func.nullif(decisive, 0)
        result = await self.session.execute(
            select(User, (win_rate * 100).label("win_rate"))
            .join(UserStats, UserStats.user_id == User.id)
            .where(User.is_banned.is_(False), decisive >= MIN_GAMES_FOR_WINRATE)
            .order_by(desc("win_rate"))
            .limit(limit)
        )
        return await self._rows_to_entries(result.all())

    async def longest_streak(self, limit: int = 10) -> list[LeaderboardEntry]:
        result = await self.session.execute(
            select(User, User.best_streak)
            .where(User.is_banned.is_(False))
            .order_by(desc(User.best_streak))
            .limit(limit)
        )
        return await self._rows_to_entries(result.all())

    # ----- Group leaderboards (restricted to a set of telegram ids) -----
    async def group_top_wins(
        self, telegram_ids: list[int], limit: int = 10
    ) -> list[LeaderboardEntry]:
        if not telegram_ids:
            return []
        result = await self.session.execute(
            select(User, UserStats.wins)
            .join(UserStats, UserStats.user_id == User.id)
            .where(User.telegram_id.in_(telegram_ids))
            .order_by(desc(UserStats.wins))
            .limit(limit)
        )
        return await self._rows_to_entries(result.all())

    # ----- Season leaderboard -----
    async def season_top(self, season_id: int, limit: int = 10) -> list[LeaderboardEntry]:
        result = await self.session.execute(
            select(User, SeasonParticipant.season_points)
            .join(SeasonParticipant, SeasonParticipant.user_id == User.id)
            .where(SeasonParticipant.season_id == season_id)
            .order_by(desc(SeasonParticipant.season_points))
            .limit(limit)
        )
        return await self._rows_to_entries(result.all())
