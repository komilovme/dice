"""Authentication middleware: load-or-create the user and enforce bans.

Injects the resolved :class:`User` (and a ``user_created`` flag) into handler
data. Deep-link referral payloads on ``/start`` are parsed here so referral
attribution happens exactly once, at account creation.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from aiogram.types import User as TgUser

from app.config.logging import get_logger
from app.services.user_service import UserService

logger = get_logger(__name__)


def _extract_referrer(event: TelegramObject) -> int | None:
    """Parse a ``/start <referrer_id>`` deep-link payload."""
    if isinstance(event, Message) and event.text and event.text.startswith("/start"):
        parts = event.text.split(maxsplit=1)
        if len(parts) == 2:
            payload = parts[1].strip()
            # Support both raw ids and "ref<id>" style payloads.
            digits = payload[3:] if payload.lower().startswith("ref") else payload
            if digits.isdigit():
                return int(digits)
    return None


class AuthMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        session = data["session"]
        redis = data.get("redis")
        service = UserService(session, redis)

        user, created = await service.get_or_create(
            tg_user, referrer_telegram_id=_extract_referrer(event)
        )
        data["user"] = user
        data["user_created"] = created

        # Enforce bans for everyone except configured admins.
        if user.is_banned and not user.is_admin:
            await self._notify_banned(event, user.ban_reason)
            return None

        return await handler(event, data)

    @staticmethod
    async def _notify_banned(event: TelegramObject, reason: str | None) -> None:
        text = "🚫 Your account is banned."
        if reason:
            text += f"\nReason: {reason}"
        if isinstance(event, Message):
            await event.answer(text)
        elif isinstance(event, CallbackQuery):
            await event.answer(text, show_alert=True)
