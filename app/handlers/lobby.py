"""Lobby handlers: create / join / start / leave and matchmaking."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import BattleMode
from app.handlers.texts import esc, render_settlement
from app.keyboards.callbacks import LobbyCB
from app.keyboards.inline import back_to_menu, lobby_kb
from app.models.lobby import Lobby
from app.models.user import User
from app.services.battle_service import BattleService
from app.services.lobby_service import LobbyService
from app.utils.exceptions import GameError
from app.utils.formatting import fmt_coins

router = Router(name="lobby")


def _render_lobby(lobby: Lobby) -> str:
    members = "\n".join(
        f"• {esc(m.user.display_name)}" + (" 👑" if m.user_id == lobby.host_id else "")
        for m in lobby.members
    )
    privacy = "🔒 Private" if lobby.is_private else "🌐 Public"
    return (
        f"🎟 <b>Lobby {lobby.code}</b> ({privacy})\n"
        f"Mode: {lobby.mode.value.title()} | Stake: {fmt_coins(lobby.stake)}\n"
        f"Players: {len(lobby.members)}/{lobby.max_players}\n\n"
        f"{members}"
    )


@router.message(Command("lobby"))
async def cmd_create_lobby(
    message: Message, user: User, session: AsyncSession, redis: Redis
) -> None:
    parts = (message.text or "").split()
    stake = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    try:
        lobby = await LobbyService(session, redis).create_lobby(
            host=user, mode=BattleMode.PUBLIC, stake=stake, chat_id=message.chat.id
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        _render_lobby(lobby) + f"\n\nShare the code <code>{lobby.code}</code> — others join with "
        f"/join {lobby.code}",
        reply_markup=lobby_kb(lobby.id, is_host=True),
    )


@router.message(Command("join"))
async def cmd_join_lobby(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /join &lt;code&gt; [password]")
        return
    code = parts[1]
    password = parts[2] if len(parts) > 2 else None
    try:
        lobby = await LobbyService(session, redis).join_lobby(
            user=user, code=code, password=password
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        _render_lobby(lobby),
        reply_markup=lobby_kb(lobby.id, is_host=lobby.host_id == user.id),
    )


@router.message(Command("matchmake"))
async def cmd_matchmake(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    stake = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    try:
        lobby = await LobbyService(session, redis).auto_match(
            user=user, mode=BattleMode.PUBLIC, stake=stake
        )
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        "🔍 Matchmaking…\n\n" + _render_lobby(lobby),
        reply_markup=lobby_kb(lobby.id, is_host=lobby.host_id == user.id),
    )


@router.callback_query(LobbyCB.filter(F.action == "refresh"))
async def cb_refresh(
    query: CallbackQuery, callback_data: LobbyCB, session: AsyncSession, redis: Redis, user: User
) -> None:
    lobby = await LobbyService(session, redis).repo.get_full(callback_data.lobby_id)
    if lobby is None:
        await query.answer("Lobby not found.", show_alert=True)
        return
    await query.message.edit_text(
        _render_lobby(lobby),
        reply_markup=lobby_kb(lobby.id, is_host=lobby.host_id == user.id),
    )
    await query.answer("Refreshed")


@router.callback_query(LobbyCB.filter(F.action == "start"))
async def cb_start(
    query: CallbackQuery, callback_data: LobbyCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    lobby_service = LobbyService(session, redis)
    lobby = await lobby_service.repo.get_full(callback_data.lobby_id)
    if lobby is None:
        await query.answer("Lobby not found.", show_alert=True)
        return
    if lobby.host_id != user.id:
        await query.answer("Only the host can start.", show_alert=True)
        return
    try:
        battle = await lobby_service.start_lobby(lobby=lobby)
        settlement = await BattleService(session, redis).auto_resolve(battle)
    except GameError as exc:
        await query.answer(exc.message, show_alert=True)
        return
    await query.message.edit_text(render_settlement(settlement), reply_markup=back_to_menu())
    await query.answer()


@router.callback_query(LobbyCB.filter(F.action == "leave"))
async def cb_leave(
    query: CallbackQuery, callback_data: LobbyCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    lobby = await LobbyService(session, redis).repo.get_full(callback_data.lobby_id)
    if lobby is None:
        await query.answer("Lobby not found.", show_alert=True)
        return
    member = next((m for m in lobby.members if m.user_id == user.id), None)
    if member is not None:
        await session.delete(member)
    await query.message.edit_text("🚪 You left the lobby.", reply_markup=back_to_menu())
    await query.answer()
