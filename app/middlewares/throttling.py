"""Throttling middleware: first line of flood protection.

Uses a Redis fixed-window counter per user. When a user exceeds the configured
rate the update is dropped (silently, except for a single warning per window) so
the bot is shielded from spam and accidental loops.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser
from redis.asyncio import Redis

from app.config.logging import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis: Redis, *, rate: int | None = None, window: int = 1) -> None:
        self.redis = redis
        self.rate = rate or settings.rate_limit_per_second
        self.window = window

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None:
            return await handler(event, data)

        key = f"throttle:{tg_user.id}"
        pipe = self.redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(key, self.window, nx=True)
        count, _ = await pipe.execute()

        if int(count) > self.rate:
            # Warn exactly once per window to avoid notification spam.
            if int(count) == self.rate + 1:
                await self._warn(event)
            logger.debug("throttled", user_id=tg_user.id, count=int(count))
            return None

        return await handler(event, data)

    @staticmethod
    async def _warn(event: TelegramObject) -> None:
        text = "⏳ Slow down a little — you're sending requests too fast."
        try:
            if isinstance(event, Message):
                await event.answer(text)
            elif isinstance(event, CallbackQuery):
                await event.answer(text, show_alert=False)
        except Exception:  # never let a warning break the pipeline
            pass
