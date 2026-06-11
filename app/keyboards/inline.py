"""Inline keyboard builders used across handlers."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.config.constants import CASES, POWERUPS
from app.keyboards.callbacks import (
    BattleCB,
    ClanCB,
    EconomyCB,
    LeaderboardCB,
    LobbyCB,
    MenuCB,
    ShopCB,
)


def main_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Profile", callback_data=MenuCB(action="profile"))
    kb.button(text="💰 Economy", callback_data=MenuCB(action="economy"))
    kb.button(text="⚔️ Battles", callback_data=MenuCB(action="battles"))
    kb.button(text="🏆 Leaderboards", callback_data=MenuCB(action="leaderboards"))
    kb.button(text="🎁 Shop", callback_data=MenuCB(action="shop"))
    kb.button(text="🛡 Clan", callback_data=MenuCB(action="clan"))
    kb.button(text="❓ Help", callback_data=MenuCB(action="help"))
    kb.adjust(2, 2, 2, 1)
    return kb.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="« Back to menu", callback_data=MenuCB(action="main"))
    return kb.as_markup()


def economy_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📅 Daily", callback_data=EconomyCB(action="daily"))
    kb.button(text="🗓 Weekly", callback_data=EconomyCB(action="weekly"))
    kb.button(text="🎰 Lucky Chest", callback_data=EconomyCB(action="chest"))
    kb.button(text="🧾 History", callback_data=EconomyCB(action="history"))
    kb.button(text="« Back", callback_data=MenuCB(action="main"))
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def battles_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Quick Duel", callback_data=BattleCB(action="quick"))
    kb.button(text="🌐 Public Battle", callback_data=BattleCB(action="public"))
    kb.button(text="« Back", callback_data=MenuCB(action="main"))
    kb.adjust(2, 1)
    return kb.as_markup()


def join_battle_kb(battle_id: int) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="⚔️ Join Battle", callback_data=BattleCB(action="join", battle_id=battle_id))
    kb.button(text="🎲 Roll", callback_data=BattleCB(action="roll", battle_id=battle_id))
    kb.adjust(2)
    return kb.as_markup()


def lobby_kb(lobby_id: int, *, is_host: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔄 Refresh", callback_data=LobbyCB(action="refresh", lobby_id=lobby_id))
    if is_host:
        kb.button(text="▶️ Start", callback_data=LobbyCB(action="start", lobby_id=lobby_id))
    kb.button(text="🚪 Leave", callback_data=LobbyCB(action="leave", lobby_id=lobby_id))
    kb.adjust(2, 1)
    return kb.as_markup()


def leaderboards_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💎 Richest", callback_data=LeaderboardCB(board="richest"))
    kb.button(text="🥇 Most Wins", callback_data=LeaderboardCB(board="wins"))
    kb.button(text="📈 Win Rate", callback_data=LeaderboardCB(board="winrate"))
    kb.button(text="🔥 Streak", callback_data=LeaderboardCB(board="streak"))
    kb.button(text="🗓 Season", callback_data=LeaderboardCB(board="season"))
    kb.button(text="« Back", callback_data=MenuCB(action="main"))
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def shop_menu() -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for code, case in CASES.items():
        kb.button(
            text=f"📦 {case.name} · {case.price:,}",
            callback_data=ShopCB(action="case", code=code),
        )
    for ptype, powerup in POWERUPS.items():
        kb.button(
            text=f"{powerup.icon} {powerup.name} · {powerup.price:,}",
            callback_data=ShopCB(action="powerup", code=str(ptype)),
        )
    kb.button(text="« Back", callback_data=MenuCB(action="main"))
    kb.adjust(1, 1, 1, 1, 2, 2, 1, 1)
    return kb.as_markup()


def clan_menu(*, in_clan: bool) -> InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if in_clan:
        kb.button(text="🏰 My Clan", callback_data=ClanCB(action="view"))
        kb.button(text="💰 Donate", callback_data=ClanCB(action="donate"))
    kb.button(text="🏆 Clan Ranking", callback_data=ClanCB(action="leaderboard"))
    kb.button(text="« Back", callback_data=MenuCB(action="main"))
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def referral_share_kb(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    """A share button that opens the bot with the user's referral payload."""
    link = f"https://t.me/{bot_username}?start=ref{user_id}"
    kb = InlineKeyboardBuilder()
    kb.add(
        InlineKeyboardButton(
            text="📨 Share invite link",
            url=f"https://t.me/share/url?url={link}",
        )
    )
    return kb.as_markup()
