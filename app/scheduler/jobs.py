"""Scheduled background jobs.

Each job opens its own short-lived DB session (it runs outside the request /
update lifecycle, so the DatabaseMiddleware does not apply here).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import delete, update

from app.config.constants import LobbyStatus
from app.config.logging import get_logger
from app.database.redis import redis_client
from app.database.session import get_session
from app.models.lobby import Lobby
from app.services.season_service import SeasonService

logger = get_logger(__name__)


async def monthly_season_rollover() -> None:
    """Finalise the current season and open the next. Runs on the 1st monthly."""
    async with get_session() as session:
        service = SeasonService(session, redis_client.client)
        result = await service.rollover()
        logger.info(
            "scheduler.season_rollover",
            new_season=result.new_season.number,
            rewarded=result.rewarded_players,
        )


async def expire_stale_lobbies() -> None:
    """Close lobbies whose expiry has passed so matchmaking stays clean."""
    now = datetime.now(UTC)
    async with get_session() as session:
        result = await session.execute(
            update(Lobby)
            .where(
                Lobby.status == LobbyStatus.OPEN,
                Lobby.expires_at.is_not(None),
                Lobby.expires_at < now,
            )
            .values(status=LobbyStatus.CLOSED)
        )
        if result.rowcount:
            logger.info("scheduler.lobbies_expired", count=result.rowcount)


async def purge_closed_lobbies() -> None:
    """Hard-delete long-closed/in-progress lobbies to keep the table small."""
    async with get_session() as session:
        result = await session.execute(
            delete(Lobby).where(Lobby.status.in_([LobbyStatus.CLOSED, LobbyStatus.IN_PROGRESS]))
        )
        if result.rowcount:
            logger.info("scheduler.lobbies_purged", count=result.rowcount)


async def refresh_leaderboard_cache() -> None:
    """Warm the Redis leaderboard cache so the first viewer isn't slow."""
    from app.services.leaderboard_service import LeaderboardService

    async with get_session() as session:
        service = LeaderboardService(session, redis_client.client)
        await service.invalidate()
        await service.richest()
        await service.most_wins()
    logger.debug("scheduler.leaderboard_cache_refreshed")
