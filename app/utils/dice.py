"""Dice utilities.

Telegram's animated dice emoji (🎲) returns a server-authoritative value in
``message.dice.value`` between 1 and 6. We never generate dice values for the
group flow — we read the value Telegram produced, which is what makes the game
provably fair and tamper-resistant.

For non-group flows (inline duels, royale, bots filling a bracket) we use a
cryptographically-strong RNG.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass

DICE_MIN = 1
DICE_MAX = 6


def roll_die() -> int:
    """Return a single fair die roll in [1, 6] using a CSPRNG."""
    return secrets.randbelow(DICE_MAX) + 1


def roll_dice(count: int) -> list[int]:
    """Roll ``count`` dice and return individual values."""
    return [roll_die() for _ in range(max(1, count))]


@dataclass(slots=True)
class RollResult:
    rolls: list[int]
    score: int

    @classmethod
    def from_rolls(cls, rolls: list[int]) -> RollResult:
        return cls(rolls=rolls, score=sum(rolls))


def score_from_telegram_value(value: int) -> int:
    """Validate and return a Telegram dice value.

    Raises ValueError if the value is outside Telegram's documented range so we
    never trust a spoofed update.
    """
    if not (DICE_MIN <= value <= DICE_MAX):
        raise ValueError(f"Invalid Telegram dice value: {value}")
    return value


def display_rolls(rolls: list[int]) -> str:
    """Render rolls as dice faces, e.g. [5, 3] -> '⚄⚂ (8)'."""
    faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    rendered = "".join(faces.get(r, "🎲") for r in rolls)
    return f"{rendered} ({sum(rolls)})"
