"""Typed callback-data factories for inline keyboards (aiogram CallbackData)."""

from __future__ import annotations

from aiogram.filters.callback_data import CallbackData


class MenuCB(CallbackData, prefix="menu"):
    action: str  # main | profile | economy | battles | leaderboards | shop | clan | help


class EconomyCB(CallbackData, prefix="eco"):
    action: str  # daily | weekly | chest | history


class BattleCB(CallbackData, prefix="btl"):
    action: str  # join | roll | cancel
    battle_id: int = 0


class BattleModeCB(CallbackData, prefix="bmode"):
    mode: str
    stake: int = 0


class LobbyCB(CallbackData, prefix="lob"):
    action: str  # join | start | leave | refresh
    lobby_id: int = 0


class ShopCB(CallbackData, prefix="shop"):
    action: str  # case | powerup | view
    code: str = ""


class LeaderboardCB(CallbackData, prefix="lb"):
    board: str  # richest | wins | winrate | streak | season


class ClanCB(CallbackData, prefix="clan"):
    action: str  # view | leaderboard | donate | leave
