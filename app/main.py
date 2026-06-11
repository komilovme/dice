"""Application entrypoint.

Wires together the bot, dispatcher, database, Redis, middlewares, handlers and
scheduler, then runs either long-polling or a webhook server depending on
configuration. Handles graceful startup and shutdown of all resources.
"""

from __future__ import annotations

import asyncio
import contextlib

from aiogram import Bot, Dispatcher

from app.bot import create_bot, create_dispatcher, set_bot_commands
from app.config.logging import configure_logging, get_logger
from app.config.settings import settings
from app.database.redis import redis_client
from app.database.session import create_engine_and_sessionmaker, dispose_engine
from app.handlers import setup_handlers
from app.middlewares import setup_middlewares
from app.scheduler import start_scheduler
from app.services.season_service import SeasonService

logger = get_logger(__name__)

try:  # uvloop massively improves throughput on Linux; optional on other OSes.
    import uvloop  # type: ignore

    uvloop.install()
except ImportError:  # pragma: no cover
    uvloop = None


async def on_startup(bot: Bot, dp: Dispatcher) -> None:
    configure_logging()
    logger.info("startup.begin", env=settings.app_env, webhook=settings.use_webhook)

    # Database + Redis
    create_engine_and_sessionmaker()
    redis = await redis_client.connect()

    # Make the redis connection available to middlewares and handlers.
    dp["redis"] = redis

    # Ensure there is an active season to attribute battles to.
    from app.database.session import get_session

    async with get_session() as session:
        await SeasonService(session, redis).ensure_active_season()

    setup_middlewares(dp, redis)
    setup_handlers(dp)
    await set_bot_commands(bot)

    if settings.run_scheduler:
        dp["scheduler"] = start_scheduler()

    logger.info("startup.complete")


async def on_shutdown(dp: Dispatcher) -> None:
    logger.info("shutdown.begin")
    scheduler = dp.get("scheduler")
    if scheduler is not None:
        scheduler.shutdown(wait=False)
    await redis_client.close()
    await dispose_engine()
    logger.info("shutdown.complete")


async def run_polling() -> None:
    bot = create_bot()
    dp = create_dispatcher()
    await on_startup(bot, dp)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await on_shutdown(dp)
        await bot.session.close()


async def run_webhook() -> None:
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web

    bot = create_bot()
    dp = create_dispatcher()
    await on_startup(bot, dp)

    await bot.set_webhook(
        url=f"{settings.webhook_url}{settings.webhook_path}",
        secret_token=settings.webhook_secret,
        drop_pending_updates=True,
        allowed_updates=dp.resolve_used_update_types(),
    )

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=settings.webhook_secret).register(
        app, path=settings.webhook_path
    )
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=settings.webapp_host, port=settings.webapp_port)
    await site.start()
    logger.info("webhook.serving", host=settings.webapp_host, port=settings.webapp_port)

    try:
        await asyncio.Event().wait()  # serve forever
    finally:
        await runner.cleanup()
        await on_shutdown(dp)
        await bot.session.close()


def main() -> None:
    runner = run_webhook if settings.use_webhook else run_polling
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(runner())


if __name__ == "__main__":
    main()
