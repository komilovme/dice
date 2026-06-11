"""Domain-level exceptions raised by the services layer.

Handlers catch :class:`GameError` (and subclasses) and translate them into
friendly Telegram messages. Anything not derived from ``GameError`` is treated
as an unexpected server error.
"""

from __future__ import annotations


class GameError(Exception):
    """Base class for expected, user-facing game errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InsufficientBalanceError(GameError):
    def __init__(self, needed: int, available: int) -> None:
        super().__init__(
            f"Insufficient balance. You need {needed:,} coins but only have {available:,}."
        )
        self.needed = needed
        self.available = available


class UserBannedError(GameError):
    def __init__(self) -> None:
        super().__init__("Your account is banned. Contact an administrator.")


class CooldownError(GameError):
    def __init__(self, retry_after: int, what: str = "action") -> None:
        super().__init__(f"Please wait {retry_after}s before your next {what}.")
        self.retry_after = retry_after


class RewardNotReadyError(GameError):
    def __init__(self, retry_after_seconds: int, reward: str) -> None:
        hours = retry_after_seconds // 3600
        minutes = (retry_after_seconds % 3600) // 60
        super().__init__(
            f"Your {reward} reward is not ready yet. Come back in {hours}h {minutes}m."
        )
        self.retry_after_seconds = retry_after_seconds


class BetLimitError(GameError):
    pass


class NotFoundError(GameError):
    pass


class ValidationError(GameError):
    pass


class PermissionError_(GameError):
    """Raised when a user lacks permission for an operation (e.g. clan role)."""
