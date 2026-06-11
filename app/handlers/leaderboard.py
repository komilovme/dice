"""Leaderboard handlers: global and seasonal rankings."""

from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.texts import render_leaderboard
from app.keyboards.callbacks import LeaderboardCB
from app.keyboards.inline import leaderboards_menu
from app.services.leaderboard_service import LeaderboardService

router = Router(name="leaderboard")


async def _fetch(service: LeaderboardService, board: str):
    match board:
        case "richest":
            return await service.richest()
        case "wins":
            return await service.most_wins()
        case "winrate":
            return await service.highest_win_rate()
        case "streak":
            return await service.longest_streak()
        case "season":
            return await service.current_season()
        case _:
            return await service.richest()


@router.message(Command("top"))
async def cmd_top(message: Message, session: AsyncSession, redis: Redis) -> None:
    service = LeaderboardService(session, redis)
    entries = await service.richest()
    await message.answer(render_leaderboard("richest", entries), reply_markup=leaderboards_menu())


@router.callback_query(LeaderboardCB.filter())
async def cb_leaderboard(
    query: CallbackQuery, callback_data: LeaderboardCB, session: AsyncSession, redis: Redis
) -> None:
    service = LeaderboardService(session, redis)
    entries = await _fetch(service, callback_data.board)
    await query.message.edit_text(
        render_leaderboard(callback_data.board, entries),
        reply_markup=leaderboards_menu(),
    )
    await query.answer()
