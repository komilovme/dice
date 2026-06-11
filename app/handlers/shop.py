"""Shop handlers: opening cases and buying powerups."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.constants import CASES, POWERUPS, PowerupType, RewardKind
from app.keyboards.callbacks import ShopCB
from app.keyboards.inline import shop_menu
from app.models.user import User
from app.services.case_service import CaseService
from app.services.powerup_service import PowerupService
from app.utils.exceptions import GameError
from app.utils.formatting import fmt_coins

router = Router(name="shop")


@router.message(Command("shop", "cases"))
async def cmd_shop(message: Message) -> None:
    await message.answer(
        "🎁 <b>Shop</b>\n\nOpen cases for cosmetics & boosters, or buy powerups.",
        reply_markup=shop_menu(),
    )


@router.callback_query(ShopCB.filter(F.action == "case"))
async def cb_open_case(
    query: CallbackQuery, callback_data: ShopCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    case = CASES.get(callback_data.code)
    if case is None:
        await query.answer("Unknown case.", show_alert=True)
        return
    try:
        result = await CaseService(session, redis).open_case(
            user=user, case_code=callback_data.code
        )
    except GameError as exc:
        await query.answer(exc.message, show_alert=True)
        return

    reward = result.reward
    if reward.kind == RewardKind.COINS:
        line = f"💰 <b>{fmt_coins(reward.coins)} coins</b>"
    else:
        line = f"{reward.kind.value.title()}: <b>{reward.label}</b>"

    await query.message.answer(
        f"📦 <b>{case.name} opened!</b>\n\n"
        f"You won: {line}\n"
        f"Balance: <b>{fmt_coins(result.new_balance)}</b>",
        reply_markup=shop_menu(),
    )
    await query.answer("🎉 Opened!")


@router.callback_query(ShopCB.filter(F.action == "powerup"))
async def cb_buy_powerup(
    query: CallbackQuery, callback_data: ShopCB, user: User, session: AsyncSession, redis: Redis
) -> None:
    try:
        ptype = PowerupType(callback_data.code)
    except ValueError:
        await query.answer("Unknown powerup.", show_alert=True)
        return
    definition = POWERUPS[ptype]
    try:
        await PowerupService(session, redis).buy(user=user, ptype=ptype)
    except GameError as exc:
        await query.answer(exc.message, show_alert=True)
        return
    await query.message.answer(
        f"{definition.icon} <b>{definition.name}</b> purchased!\n"
        f"{definition.description}\n"
        f"Cost: {fmt_coins(definition.price)} coins",
        reply_markup=shop_menu(),
    )
    await query.answer("✅ Purchased")
