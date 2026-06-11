"""Leaderboard service with short-lived Redis caching.

Leaderboard queries are read-heavy and identical for many users, so results are
cached in Redis for a short TTL to shield PostgreSQL from repeated scans.
"""

from __future__ import annotations

import orjson

from app.repositories.leaderboard_repository import (
    LeaderboardEntry,
    LeaderboardRepository,
)
from app.repositories.season_repository import SeasonRepository
from app.services.base import BaseService

CACHE_TTL = 60  # seconds


class LeaderboardService(BaseService):
    def __init__(self, session, redis=None) -> None:  # noqa: ANN001
        super().__init__(session, redis)
        self.repo = LeaderboardRepository(session)
        self.seasons = SeasonRepository(session)

    async def _cached(self, key: str, fetch, limit: int) -> list[LeaderboardEntry]:
        if self.redis is not None:
            raw = await self.redis.get(f"lb:{key}:{limit}")
            if raw:
                data = orjson.loads(raw)
                return [LeaderboardEntry(**row) for row in data]

        entries = await fetch(limit)

        if self.redis is not None and entries:
            payload = orjson.dumps([e.__dict__ for e in entries])
            await self.redis.set(f"lb:{key}:{limit}", payload, ex=CACHE_TTL)
        return entries

    async def richest(self, limit: int = 10) -> list[LeaderboardEntry]:
        return await self._cached("richest", self.repo.richest, limit)

    async def most_wins(self, limit: int = 10) -> list[LeaderboardEntry]:
        return await self._cached("most_wins", self.repo.most_wins, limit)

    async def highest_win_rate(self, limit: int = 10) -> list[LeaderboardEntry]:
        return await self._cached("win_rate", self.repo.highest_win_rate, limit)

    async def longest_streak(self, limit: int = 10) -> list[LeaderboardEntry]:
        return await self._cached("streak", self.repo.longest_streak, limit)

    async def group_top(self, telegram_ids: list[int], limit: int = 10) -> list[LeaderboardEntry]:
        # Group boards are not cached (membership is request-specific).
        return await self.repo.group_top_wins(telegram_ids, limit)

    async def current_season(self, limit: int = 10) -> list[LeaderboardEntry]:
        season = await self.seasons.get_active()
        if season is None:
            return []
        return await self.repo.season_top(season.id, limit)

    async def invalidate(self) -> None:
        """Drop all cached leaderboards (call after large balance changes)."""
        if self.redis is None:
            return
        async for key in self.redis.scan_iter("lb:*"):
            await self.redis.delete(key)
