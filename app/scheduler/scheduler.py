"""APScheduler setup and lifecycle management.

A single AsyncIOScheduler runs alongside the bot's event loop. In a multi-replica
deployment, only ONE replica should run the scheduler (set RUN_SCHEDULER=1 for a
dedicated worker) to avoid duplicate season rollovers / reward grants.
"""

from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.config.logging import get_logger
from app.config.settings import settings
from app.scheduler.jobs import (
    expire_stale_lobbies,
    monthly_season_rollover,
    purge_closed_lobbies,
    refresh_leaderboard_cache,
)

logger = get_logger(__name__)


def create_scheduler() -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.tz)

    # Season rollover: 00:05 UTC on the 1st of every month.
    scheduler.add_job(
        monthly_season_rollover,
        CronTrigger(day=1, hour=0, minute=5),
        id="season_rollover",
        replace_existing=True,
        misfire_grace_time=3_600,
    )

    # Expire stale lobbies every 5 minutes.
    scheduler.add_job(
        expire_stale_lobbies,
        IntervalTrigger(minutes=5),
        id="expire_lobbies",
        replace_existing=True,
    )

    # Purge closed lobbies daily at 04:00.
    scheduler.add_job(
        purge_closed_lobbies,
        CronTrigger(hour=4, minute=0),
        id="purge_lobbies",
        replace_existing=True,
    )

    # Refresh leaderboard cache every 2 minutes.
    scheduler.add_job(
        refresh_leaderboard_cache,
        IntervalTrigger(minutes=2),
        id="refresh_leaderboards",
        replace_existing=True,
    )

    return scheduler


def start_scheduler() -> AsyncIOScheduler:
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("scheduler.started", jobs=[j.id for j in scheduler.get_jobs()])
    return scheduler
