"""Bot & Dispatcher factory.

Builds the Aiogram ``Bot`` (HTML parse mode) and ``Dispatcher`` (Redis-backed
FSM storage so state survives restarts and is shared across replicas).
"""

from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.types import BotCommand

from app.config.settings import settings

PUBLIC_COMMANDS = [
    BotCommand(command="start", description="Open the main menu"),
    BotCommand(command="profile", description="View your profile"),
    BotCommand(command="balance", description="Check your coins"),
    BotCommand(command="daily", description="Claim daily reward"),
    BotCommand(command="weekly", description="Claim weekly reward"),
    BotCommand(command="chest", description="Open a lucky chest"),
    BotCommand(command="play", description="Quick duel vs the house"),
    BotCommand(command="duel", description="Start a group dice battle"),
    BotCommand(command="lobby", description="Create a lobby"),
    BotCommand(command="join", description="Join a lobby by code"),
    BotCommand(command="top", description="Leaderboards"),
    BotCommand(command="clan", description="Clan menu"),
    BotCommand(command="help", description="How to play"),
]


def create_bot() -> Bot:
    return Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def create_dispatcher() -> Dispatcher:
    storage = RedisStorage.from_url(
        settings.redis_url,
        connection_kwargs={"decode_responses": True},
    )
    return Dispatcher(storage=storage)


async def set_bot_commands(bot: Bot) -> None:
    await bot.set_my_commands(PUBLIC_COMMANDS)
