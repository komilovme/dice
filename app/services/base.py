"""Base class for services.

A service owns business logic for one domain area. It receives the request's
``AsyncSession`` (so all repository calls share one transaction) and an optional
Redis connection for caching / locks / rate limiting.
"""

from __future__ import annotations

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    def __init__(self, session: AsyncSession, redis: Redis | None = None) -> None:
        self.session = session
        self.redis = redis
