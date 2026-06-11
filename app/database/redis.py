"""Async Redis client wrapper.

Redis is used for:
  * Aiogram FSM storage (see app.bot factory)
  * Rate limiting / anti-cheat cooldowns (atomic INCR + EXPIRE)
  * Distributed locks (matchmaking, jackpot settlement)
  * Hot leaderboard caching (sorted sets)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from redis.asyncio import Redis
from redis.asyncio.lock import Lock

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class RedisClient:
    """Thin singleton-style wrapper around an async Redis connection pool."""

    def __init__(self) -> None:
        self._redis: Redis | None = None

    async def connect(self) -> Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                settings.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=100,
                health_check_interval=30,
            )
            await self._redis.ping()
            logger.info("redis.connected", url=settings.redis_host)
        return self._redis

    @property
    def client(self) -> Redis:
        if self._redis is None:
            raise RuntimeError("Redis is not connected. Call connect() first.")
        return self._redis

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            logger.info("redis.closed")
            self._redis = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    async def incr_with_ttl(self, key: str, ttl_seconds: int) -> int:
        """Atomically increment a counter and ensure a TTL is set.

        Used heavily by the anti-cheat / throttling layer.
        """
        pipe = self.client.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, ttl_seconds, nx=True)
        result = await pipe.execute()
        return int(result[0])

    @asynccontextmanager
    async def lock(
        self,
        name: str,
        *,
        timeout: float = 10.0,  # noqa: ASYNC109 - Redis lock TTL, not an asyncio timeout
        blocking_timeout: float = 5.0,
    ) -> AsyncIterator[Lock]:
        """Distributed lock context manager for critical sections."""
        lock = self.client.lock(f"lock:{name}", timeout=timeout, blocking_timeout=blocking_timeout)
        acquired = await lock.acquire()
        if not acquired:
            raise TimeoutError(f"Could not acquire lock '{name}'")
        try:
            yield lock
        finally:
            try:
                await lock.release()
            except Exception:  # lock may have expired
                logger.warning("redis.lock_release_failed", lock=name)


redis_client = RedisClient()


async def get_redis() -> Redis:
    """Return the connected redis client (FastAPI/aiogram dependency style)."""
    return await redis_client.connect()
