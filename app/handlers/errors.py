"""Global error handler.

Catches exceptions that bubble out of handlers. Expected ``GameError`` instances
are turned into friendly messages; anything else is logged with full context and
the user receives a generic apology so the bot never goes silent on a crash.
"""

from __future__ import annotations

from aiogram import Dispatcher
from aiogram.types import CallbackQuery, ErrorEvent, Message

from app.config.logging import get_logger
from app.utils.exceptions import GameError

logger = get_logger(__name__)


async def on_error(event: ErrorEvent) -> bool:
    exc = event.exception
    update = event.update

    message: Message | None = None
    callback: CallbackQuery | None = None
    if update.message is not None:
        message = update.message
    elif update.callback_query is not None:
        callback = update.callback_query
        message = callback.message

    if isinstance(exc, GameError):
        text = f"⚠️ {exc.message}"
        try:
            if callback is not None:
                await callback.answer(exc.message, show_alert=True)
            elif message is not None:
                await message.answer(text)
        except Exception:
            logger.warning("error_reply_failed")
        return True

    logger.exception(
        "unhandled_exception",
        error=str(exc),
        update_id=getattr(update, "update_id", None),
    )
    try:
        if callback is not None:
            await callback.answer("Something went wrong. Please try again.", show_alert=True)
        elif message is not None:
            await message.answer("😵 Something went wrong. Please try again later.")
    except Exception:
        logger.warning("error_reply_failed")
    return True


def register_error_handler(dp: Dispatcher) -> None:
    dp.errors.register(on_error)
