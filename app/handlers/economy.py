"""Economy handlers: daily / weekly / chest rewards, balance and history."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import TransactionType
from app.keyboards.callbacks import EconomyCB
from app.keyboards.inline import back_to_menu, economy_menu
from app.models.user import User
from app.services.economy_service import EconomyService
from app.utils.exceptions import GameError
from app.utils.formatting import fmt_coins

router = Router(name="economy")

_TXN_LABELS = {
    TransactionType.SIGNUP_BONUS: "🎁 Welcome bonus",
    TransactionType.DAILY_REWARD: "📅 Daily",
    TransactionType.WEEKLY_REWARD: "🗓 Weekly",
    TransactionType.REFERRAL_REWARD: "👥 Referral",
    TransactionType.ACHIEVEMENT_REWARD: "🏅 Achievement",
    TransactionType.CHEST_REWARD: "🎰 Lucky chest",
    TransactionType.CASE_OPEN: "📦 Case",
    TransactionType.CASE_REWARD: "📦 Case reward",
    TransactionType.BATTLE_STAKE: "⚔️ Stake",
    TransactionType.BATTLE_WIN: "🏆 Battle win",
    TransactionType.BATTLE_REFUND: "↩️ Refund",
    TransactionType.POWERUP_PURCHASE: "✨ Powerup",
    TransactionType.CLAN_DONATION: "🛡 Clan donation",
    TransactionType.CLAN_WITHDRAW: "🛡 Clan",
    TransactionType.SEASON_REWARD: "🗓 Season reward",
    TransactionType.ADMIN_GRANT: "🛠 Admin grant",
    TransactionType.ADMIN_REMOVE: "🛠 Admin removal",
    TransactionType.HOUSE_EDGE: "🏛 House edge",
}


# ---------------------------------------------------------------------------
# Daily
# ---------------------------------------------------------------------------
async def _do_daily(user: User, session: AsyncSession, redis: Redis) -> str:
    result = await EconomyService(session, redis).claim_daily(user)
    return (
        f"📅 <b>Daily reward claimed!</b>\n\n"
        f"+{fmt_coins(result.amount)} coins (streak day {result.streak_day})\n"
        f"New balance: <b>{fmt_coins(result.new_balance)}</b>"
    )


@router.message(Command("daily"))
async def cmd_daily(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        text = await _do_daily(user, session, redis)
    except GameError as exc:
        text = f"⏳ {exc.message}"
    await message.answer(text, reply_markup=back_to_menu())


@router.callback_query(EconomyCB.filter(F.action == "daily"))
async def cb_daily(query: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        text = await _do_daily(user, session, redis)
    except GameError as exc:
        text = f"⏳ {exc.message}"
    await query.message.edit_text(text, reply_markup=economy_menu())
    await query.answer()


# ---------------------------------------------------------------------------
# Weekly
# ---------------------------------------------------------------------------
async def _do_weekly(user: User, session: AsyncSession, redis: Redis) -> str:
    result = await EconomyService(session, redis).claim_weekly(user)
    return (
        f"🗓 <b>Weekly reward claimed!</b>\n\n"
        f"+{fmt_coins(result.amount)} coins\n"
        f"New balance: <b>{fmt_coins(result.new_balance)}</b>"
    )


@router.message(Command("weekly"))
async def cmd_weekly(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        text = await _do_weekly(user, session, redis)
    except GameError as exc:
        text = f"⏳ {exc.message}"
    await message.answer(text, reply_markup=back_to_menu())


@router.callback_query(EconomyCB.filter(F.action == "weekly"))
async def cb_weekly(query: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        text = await _do_weekly(user, session, redis)
    except GameError as exc:
        text = f"⏳ {exc.message}"
    await query.message.edit_text(text, reply_markup=economy_menu())
    await query.answer()


# ---------------------------------------------------------------------------
# Lucky chest
# ---------------------------------------------------------------------------
async def _do_chest(user: User, session: AsyncSession, redis: Redis) -> str:
    result = await EconomyService(session, redis).open_lucky_chest(user)
    return (
        f"🎰 <b>Lucky chest opened!</b>\n\n"
        f"You found <b>{fmt_coins(result.amount)}</b> coins!\n"
        f"New balance: <b>{fmt_coins(result.new_balance)}</b>"
    )


@router.message(Command("chest"))
async def cmd_chest(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        text = await _do_chest(user, session, redis)
    except GameError as exc:
        text = f"⏳ {exc.message}"
    await message.answer(text, reply_markup=back_to_menu())


@router.callback_query(EconomyCB.filter(F.action == "chest"))
async def cb_chest(query: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    try:
        text = await _do_chest(user, session, redis)
    except GameError as exc:
        text = f"⏳ {exc.message}"
    await query.message.edit_text(text, reply_markup=economy_menu())
    await query.answer()


# ---------------------------------------------------------------------------
# Balance & history
# ---------------------------------------------------------------------------
@router.message(Command("balance"))
async def cmd_balance(message: Message, user: User) -> None:
    await message.answer(
        f"💰 Your balance: <b>{fmt_coins(user.balance)}</b> coins",
        reply_markup=back_to_menu(),
    )


def _render_history(transactions) -> str:
    if not transactions:
        return "🧾 <b>Transaction history</b>\n\nNo transactions yet."
    lines = ["🧾 <b>Recent transactions</b>", ""]
    for txn in transactions:
        label = _TXN_LABELS.get(txn.type, str(txn.type))
        sign = "+" if txn.amount >= 0 else ""
        lines.append(f"{label}: <b>{sign}{fmt_coins(txn.amount)}</b>")
    return "\n".join(lines)


@router.message(Command("history"))
async def cmd_history(message: Message, user: User, session: AsyncSession, redis: Redis) -> None:
    txns = await EconomyService(session, redis).history(user.id, limit=15)
    await message.answer(_render_history(txns), reply_markup=back_to_menu())


@router.callback_query(EconomyCB.filter(F.action == "history"))
async def cb_history(query: CallbackQuery, user: User, session: AsyncSession, redis: Redis) -> None:
    txns = await EconomyService(session, redis).history(user.id, limit=15)
    await query.message.edit_text(_render_history(txns), reply_markup=economy_menu())
    await query.answer()
