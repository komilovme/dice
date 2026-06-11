"""Middleware registration.

Order matters. For each incoming message / callback we run:
  1. ThrottlingMiddleware  - drop floods before doing any DB work
  2. DatabaseMiddleware     - open a transactional session for the update
  3. AuthMiddleware         - load/create the user, enforce bans

Outer middlewares run first, so they are registered in that order.
"""

from __future__ import annotations

from aiogram import Dispatcher
from redis.asyncio import Redis

from app.middlewares.auth import AuthMiddleware
from app.middlewares.database import DatabaseMiddleware
from app.middlewares.throttling import ThrottlingMiddleware

__all__ = [
    "AuthMiddleware",
    "DatabaseMiddleware",
    "ThrottlingMiddleware",
    "setup_middlewares",
]


def setup_middlewares(dp: Dispatcher, redis: Redis) -> None:
    """Attach middlewares to the message and callback_query observers."""
    throttling = ThrottlingMiddleware(redis)
    database = DatabaseMiddleware()
    auth = AuthMiddleware()

    for observer in (dp.message, dp.callback_query):
        observer.middleware(throttling)
        observer.middleware(database)
        observer.middleware(auth)
