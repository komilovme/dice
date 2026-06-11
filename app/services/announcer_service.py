"""AI Announcer: generates fun, context-aware battle commentary.

This is a deterministic, rule-based "AI" announcer that inspects the shape of a
battle result (margin of victory, high rolls, streaks, comebacks) and selects a
fitting hype phrase. It is intentionally dependency-free and synchronous so it
can be called from anywhere cheaply. The phrase banks live in constants so the
voice of the bot can be tuned without code changes.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

from app.config.constants import ANNOUNCER
from app.utils.dice import DICE_MAX


@dataclass(slots=True)
class AnnouncerContext:
    winner_score: int
    loser_score: int
    dice_per_player: int
    winner_streak: int
    is_new_streak_leader: bool = False
    winner_was_behind: bool = False  # had a lower partial roll earlier


class AnnouncerService:
    """Selects hype messages for battle outcomes."""

    @staticmethod
    def _pick(bank: tuple[str, ...]) -> str:
        return secrets.choice(bank)

    def announce(self, ctx: AnnouncerContext) -> str:
        max_possible = DICE_MAX * max(1, ctx.dice_per_player)
        margin = ctx.winner_score - ctx.loser_score

        # Priority order: legendary > streak leader > comeback > blowout >
        # high roll > close win.
        if ctx.winner_score >= max_possible and ctx.dice_per_player > 1:
            return self._pick(ANNOUNCER.legendary)
        if ctx.is_new_streak_leader or ctx.winner_streak >= 5:
            return self._pick(ANNOUNCER.streak)
        if ctx.winner_was_behind:
            return self._pick(ANNOUNCER.comeback)
        if margin >= max(3, max_possible // 2):
            return self._pick(ANNOUNCER.blowout)
        if ctx.winner_score >= max_possible - 1:
            return self._pick(ANNOUNCER.high_roll)
        return self._pick(ANNOUNCER.close_win)

    def draw_message(self) -> str:
        return "🤝 It's a tie! The dice couldn't decide."
