"""Reusable message renderers (HTML parse mode).

Centralising presentation keeps handlers thin and the bot's voice consistent.
"""

from __future__ import annotations

import html

from app.config.constants import RANK_TIERS, Rank
from app.repositories.leaderboard_repository import LeaderboardEntry
from app.services.battle_service import BattleSettlement
from app.services.ranking_service import next_tier
from app.services.user_service import ProfileView
from app.utils.formatting import fmt_coins, progress_bar


def esc(text: str | None) -> str:
    return html.escape(text or "")


def rank_icon(rank: Rank | str) -> str:
    rank = Rank(rank)
    return next((t.icon for t in RANK_TIERS if t.rank == rank), "🥉")


def render_welcome(display_name: str, balance: int, created: bool) -> str:
    if created:
        return (
            f"🎲 <b>Welcome to Dice Arena, {esc(display_name)}!</b>\n\n"
            f"You've received a welcome bonus of <b>{fmt_coins(balance)}</b> coins.\n\n"
            "Challenge players to dice battles, climb the ranks, open cases, "
            "join a clan and top the leaderboards!\n\n"
            "Use the menu below to get started."
        )
    return (
        f"🎲 <b>Welcome back, {esc(display_name)}!</b>\n\n"
        f"Balance: <b>{fmt_coins(balance)}</b> coins\n\n"
        "What would you like to do?"
    )


def render_profile(view: ProfileView) -> str:
    u = view.user
    stats = u.stats
    nxt = next_tier(Rank(u.rank))
    rank_line = f"{view.rank_icon} <b>{Rank(u.rank).value.title()}</b>"
    if nxt is not None:
        rank_line += (
            f"  →  {nxt.icon} {nxt.rank.value.title()}\n"
            f"XP: {progress_bar(view.xp_into, view.xp_needed)}  "
            f"({fmt_coins(u.xp)} XP)"
        )
    else:
        rank_line += f"  (max rank)\nXP: {fmt_coins(u.xp)}"

    return (
        f"👤 <b>{esc(u.display_name)}</b>"
        + (f"  <i>{esc(u.active_title)}</i>" if u.active_title else "")
        + "\n\n"
        f"{rank_line}\n\n"
        f"💰 Balance: <b>{fmt_coins(u.balance)}</b> coins\n"
        f"🎮 Games: {fmt_coins(stats.total_games)}\n"
        f"🥇 Wins: {fmt_coins(stats.wins)}  |  ❌ Losses: {fmt_coins(stats.losses)}\n"
        f"📈 Win rate: <b>{stats.win_rate_pct}%</b>\n"
        f"🔥 Streak: {u.current_streak} (best {u.best_streak})\n"
        f"💎 Biggest win: {fmt_coins(stats.biggest_win)}\n"
        f"🏅 Achievements: {view.achievements_unlocked}/{view.achievements_total}\n"
        f"🛡 Clan: {esc(view.clan_name) if view.clan_name else '—'}\n"
        f"👥 Referrals: {u.referral_count}"
    )


def render_settlement(settlement: BattleSettlement) -> str:
    """Render the clean, formatted battle result posted to the chat."""
    lines = ["🎲 <b>Dice Battle</b>", ""]
    for p in settlement.participants:
        marker = "🏆 " if p.is_winner else ""
        lines.append(f"{marker}{esc(p.display_name)}: <b>{p.score}</b>")
    lines.append("")

    if settlement.is_draw:
        lines.append("🤝 <b>Draw!</b> Stakes refunded.")
    else:
        winners = settlement.winners
        names = ", ".join(esc(w.display_name) for w in winners)
        payout = winners[0].payout if winners else 0
        lines.append(f"🏆 <b>Winner:</b> {names}")
        if payout:
            lines.append(f"💰 <b>Reward:</b> {fmt_coins(payout)} Coins")

    if settlement.announcer_message:
        lines.append("")
        lines.append(settlement.announcer_message)

    # Rank promotions
    for _user_id, new_rank in settlement.promotions.items():
        lines.append(f"⬆️ Promoted to <b>{Rank(new_rank).value.title()}</b>!")

    # Achievement unlocks
    for unlocks in settlement.unlocked.values():
        for ach in unlocks:
            lines.append(f"{ach.icon} Achievement unlocked: <b>{esc(ach.name)}</b>")

    return "\n".join(lines)


_BOARD_TITLES = {
    "richest": "💎 Richest Players",
    "wins": "🥇 Most Wins",
    "winrate": "📈 Highest Win Rate",
    "streak": "🔥 Longest Streak",
    "season": "🗓 Season Leaderboard",
}
_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


def render_leaderboard(board: str, entries: list[LeaderboardEntry]) -> str:
    title = _BOARD_TITLES.get(board, "🏆 Leaderboard")
    if not entries:
        return f"<b>{title}</b>\n\nNo data yet. Be the first!"
    suffix = "%" if board == "winrate" else ""
    lines = [f"<b>{title}</b>", ""]
    for e in entries:
        medal = _MEDALS.get(e.rank, f"{e.rank}.")
        value = f"{e.value:.1f}" if board == "winrate" else fmt_coins(int(e.value))
        lines.append(f"{medal} {esc(e.display_name)} — <b>{value}{suffix}</b>")
    return "\n".join(lines)
