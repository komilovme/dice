"""Handlers package: aggregates all feature routers into one root router.

Registration order matters — more specific / privileged routers are included
first so their handlers take precedence during update routing.
"""

from __future__ import annotations

from aiogram import Dispatcher, Router

from app.handlers import (
    admin,
    battles,
    clan,
    common,
    economy,
    leaderboard,
    lobby,
    shop,
)
from app.handlers.errors import register_error_handler


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_routers(
        admin.router,
        common.router,
        economy.router,
        battles.router,
        lobby.router,
        clan.router,
        leaderboard.router,
        shop.router,
    )
    return root


def setup_handlers(dp: Dispatcher) -> None:
    dp.include_router(build_root_router())
    register_error_handler(dp)
