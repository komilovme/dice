"""Clan handlers: creation, joining, donations, and rankings."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.texts import esc
from app.keyboards.callbacks import ClanCB
from app.keyboards.inline import back_to_menu, clan_menu
from app.models.clan import Clan
from app.models.user import User
from app.services.clan_service import ClanService
from app.utils.exceptions import GameError
from app.utils.formatting import fmt_coins

router = Router(name="clan")


def _render_clan(clan: Clan) -> str:
    members = "\n".join(
        f"• {esc(m.user.display_name)} ({m.role.value}) — {fmt_coins(m.contributed)} donated"
        for m in sorted(clan.members, key=lambda m: m.contributed, reverse=True)[:15]
    )
    return (
        f"{clan.emblem} <b>{esc(clan.name)}</b> [{esc(clan.tag)}]\n"
        f"{esc(clan.description) if clan.description else ''}\n\n"
        f"🏆 Points: {fmt_coins(clan.total_points)}\n"
        f"💰 Treasury: {fmt_coins(clan.treasury)}\n"
        f"⚔️ Wars won: {clan.wars_won}\n"
        f"👥 Members: {clan.member_count}/{clan.max_members}\n\n"
        f"{members}"
    )


@router.message(Command("createclan"))
async def cmd_create_clan(
    message: Message, user: User, session: AsyncSession, redis: Redis
) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("Usage: /createclan &lt;TAG&gt; &lt;name&gt;")
        return
    tag, name = parts[1], parts[2]
    try:
        clan = await ClanService(session, redis).create_clan(leader=user, name=name, tag=tag)
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        f"🛡 Clan <b>{esc(clan.name)}</b> [{esc(clan.tag)}] founded! Invite members with your tag.",
        reply_markup=back_to_menu(),
    )


@router.message(Command("joinclan"))
async def cmd_join_clan(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2:
        await message.answer("Usage: /joinclan &lt;TAG&gt;")
        return
    try:
        clan = await ClanService(session, redis).join_clan(user=user, tag=parts[1])
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        f"🛡 You joined <b>{esc(clan.name)}</b> [{esc(clan.tag)}]!",
        reply_markup=back_to_menu(),
    )


@router.message(Command("donate"))
async def cmd_donate(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("Usage: /donate &lt;amount&gt;")
        return
    try:
        treasury = await ClanService(session, redis).donate(user=user, amount=int(parts[1]))
    except GameError as exc:
        await message.answer(f"⚠️ {exc.message}")
        return
    await message.answer(
        f"💰 Donation received! Clan treasury: <b>{fmt_coins(treasury)}</b>",
        reply_markup=back_to_menu(),
    )


@router.message(Command("clantop"))
async def cmd_clan_top(message: Message, session: AsyncSession, redis: Redis) -> None:
    await _send_clan_leaderboard(message.answer, session, redis)


async def _send_clan_leaderboard(reply, session, redis) -> None:
    clans = await ClanService(session, redis).leaderboard()
    if not clans:
        await reply("🏆 <b>Clan Ranking</b>\n\nNo clans yet. Found one with /createclan!")
        return
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    lines = ["🏆 <b>Clan Ranking</b>", ""]
    for i, clan in enumerate(clans, start=1):
        medal = medals.get(i, f"{i}.")
        lines.append(
            f"{medal} {clan.emblem} {esc(clan.name)} [{esc(clan.tag)}] — "
            f"<b>{fmt_coins(clan.total_points)}</b> pts"
        )
    await reply("\n".join(lines))


@router.callback_query(ClanCB.filter(F.action == "view"))
async def cb_view_clan(
    query: CallbackQuery, user: User, session: AsyncSession, redis: Redis
) -> None:
    clan = await ClanService(session, redis).my_clan(user)
    if clan is None:
        await query.answer("You are not in a clan.", show_alert=True)
        return
    await query.message.edit_text(_render_clan(clan), reply_markup=back_to_menu())
    await query.answer()


@router.callback_query(ClanCB.filter(F.action == "leaderboard"))
async def cb_clan_leaderboard(query: CallbackQuery, session: AsyncSession, redis: Redis) -> None:
    async def reply(text: str) -> None:
        await query.message.edit_text(text, reply_markup=clan_menu(in_clan=True))

    await _send_clan_leaderboard(reply, session, redis)
    await query.answer()


@router.callback_query(ClanCB.filter(F.action == "donate"))
async def cb_donate_prompt(query: CallbackQuery) -> None:
    await query.answer()
    await query.message.answer(
        "💰 To donate, send /donate &lt;amount&gt; (e.g. <code>/donate 500</code>).",
        reply_markup=back_to_menu(),
    )
