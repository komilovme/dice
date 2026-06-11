"""Filter that allows only configured bot administrators."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import Message

from app.config.settings import settings


class IsAdminFilter(BaseFilter):
    """Passes only if the message author is a configured admin id."""

    async def __call__(self, message: Message) -> bool:
        if message.from_user is None:
            return False
        return settings.is_admin(message.from_user.id)
