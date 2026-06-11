"""Async SQLAlchemy engine and session management.

A single ``AsyncEngine`` and ``async_sessionmaker`` are created at startup and
reused for the whole process. The :func:`get_session` async context manager
provides a transactional scope used by services and the DB middleware.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


def create_engine_and_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Initialise the global engine + session factory (idempotent)."""
    global _engine, _sessionmaker

    if _sessionmaker is not None:
        return _sessionmaker

    _engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout,
        pool_pre_ping=True,  # gracefully recycle dead connections
        pool_recycle=1_800,  # recycle every 30 minutes
    )
    _sessionmaker = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        autoflush=False,
    )
    logger.info("database.engine_initialised", pool_size=settings.db_pool_size)
    return _sessionmaker


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the session factory, initialising it on first use."""
    if _sessionmaker is None:
        return create_engine_and_sessionmaker()
    return _sessionmaker


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """Provide a transactional session scope.

    Commits on success, rolls back on exception, and always closes the session.
    """
    sessionmaker = get_sessionmaker()
    session = sessionmaker()
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose of the engine and its connection pool on shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        logger.info("database.engine_disposed")
    _engine = None
    _sessionmaker = None
