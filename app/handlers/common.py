"""Common handlers: /start, /help, /profile and top-level menu navigation."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.handlers.texts import render_profile, render_welcome
from app.keyboards.callbacks import MenuCB
from app.keyboards.inline import (
    back_to_menu,
    battles_menu,
    clan_menu,
    economy_menu,
    leaderboards_menu,
    main_menu,
    shop_menu,
)
from app.models.user import User
from app.services.clan_service import ClanService
from app.services.user_service import UserService

router = Router(name="common")

HELP_TEXT = (
    "🎲 <b>Dice Arena — Help</b>\n\n"
    "<b>General</b>\n"
    "/start — open the main menu\n"
    "/profile — view your profile\n"
    "/balance — check your coins\n\n"
    "<b>Economy</b>\n"
    "/daily — claim your daily reward\n"
    "/weekly — claim your weekly reward\n"
    "/chest — open a free lucky chest\n\n"
    "<b>Battles</b>\n"
    "/duel &lt;bet&gt; — start a dice battle in this chat, then both players send 🎲\n"
    "/public &lt;bet&gt; — create/join a public battle\n\n"
    "<b>Lobbies</b>\n"
    "/lobby &lt;bet&gt; — create a lobby\n"
    "/join &lt;code&gt; — join a lobby by code\n\n"
    "<b>Clans</b>\n"
    "/clan — clan menu\n"
    "/createclan &lt;TAG&gt; &lt;name&gt; — found a clan\n\n"
    "<b>Leaderboards</b>\n"
    "/top — view leaderboards\n\n"
    "In group chats, just send the 🎲 dice emoji during an open battle — "
    "the bot reads it, settles the match and posts a clean result."
)


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, user_created: bool) -> None:
    await message.answer(
        render_welcome(user.display_name, user.balance, user_created),
        reply_markup=main_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT, reply_markup=back_to_menu())


@router.message(Command("profile"))
async def cmd_profile(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    view = await UserService(session, redis).build_profile(user)
    await message.answer(render_profile(view), reply_markup=back_to_menu())


@router.callback_query(MenuCB.filter(F.action == "main"))
async def cb_main(query: CallbackQuery, user: User) -> None:
    await query.message.edit_text(
        render_welcome(user.display_name, user.balance, created=False),
        reply_markup=main_menu(),
    )
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "profile"))
async def cb_profile(query: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    view = await UserService(session, redis).build_profile(user)
    await query.message.edit_text(render_profile(view), reply_markup=back_to_menu())
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "economy"))
async def cb_economy(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "💰 <b>Economy</b>\n\nClaim rewards and review your transactions.",
        reply_markup=economy_menu(),
    )
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "battles"))
async def cb_battles(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "⚔️ <b>Battles</b>\n\nPick a mode. In groups you can also just send 🎲 "
        "during an open battle.",
        reply_markup=battles_menu(),
    )
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "leaderboards"))
async def cb_leaderboards(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "🏆 <b>Leaderboards</b>\n\nChoose a ranking to view.",
        reply_markup=leaderboards_menu(),
    )
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "shop"))
async def cb_shop(query: CallbackQuery) -> None:
    await query.message.edit_text(
        "🎁 <b>Shop</b>\n\nOpen cases for cosmetics & boosters, or buy powerups.",
        reply_markup=shop_menu(),
    )
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "clan"))
async def cb_clan(query: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    clan = await ClanService(session, redis).my_clan(user)
    await query.message.edit_text(
        "🛡 <b>Clans</b>\n\nTeam up, fill a treasury and climb the clan ranking.",
        reply_markup=clan_menu(in_clan=clan is not None),
    )
    await query.answer()


@router.callback_query(MenuCB.filter(F.action == "help"))
async def cb_help(query: CallbackQuery) -> None:
    await query.message.edit_text(HELP_TEXT, reply_markup=back_to_menu())
    await query.answer()
