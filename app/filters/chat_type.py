"""Filter messages by chat type (private vs group/supergroup)."""

from __future__ import annotations

from collections.abc import Sequence

from aiogram.filters import BaseFilter
from aiogram.types import Message


class ChatTypeFilter(BaseFilter):
    """Match messages whose chat type is in the allowed set.

    Usage::

        @router.message(ChatTypeFilter("private"))
        @router.message(ChatTypeFilter({"group", "supergroup"}))
    """

    def __init__(self, chat_types: str | Sequence[str]) -> None:
        if isinstance(chat_types, str):
            chat_types = {chat_types}
        self.chat_types = set(chat_types)

    async def __call__(self, message: Message) -> bool:
        return message.chat.type in self.chat_types
