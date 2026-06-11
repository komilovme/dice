"""Presentation helpers for formatting numbers, durations and progress bars."""

from __future__ import annotations


def fmt_coins(amount: int) -> str:
    """Format a coin amount with thousands separators, e.g. 12345 -> '12,345'."""
    return f"{amount:,}"


def fmt_compact(amount: int) -> str:
    """Compact number formatting, e.g. 1500 -> '1.5K', 2_300_000 -> '2.3M'."""
    abs_amount = abs(amount)
    sign = "-" if amount < 0 else ""
    if abs_amount < 1_000:
        return f"{sign}{abs_amount}"
    if abs_amount < 1_000_000:
        return f"{sign}{abs_amount / 1_000:.1f}K".replace(".0K", "K")
    if abs_amount < 1_000_000_000:
        return f"{sign}{abs_amount / 1_000_000:.1f}M".replace(".0M", "M")
    return f"{sign}{abs_amount / 1_000_000_000:.1f}B".replace(".0B", "B")


def fmt_duration(seconds: int) -> str:
    """Human-readable duration, e.g. 3725 -> '1h 2m'."""
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def progress_bar(current: int, total: int, width: int = 10) -> str:
    """Render a unicode progress bar, e.g. '█████░░░░░ 50%'."""
    ratio = 0.0 if total <= 0 else max(0.0, min(1.0, current / total))
    filled = round(ratio * width)
    return f"{'█' * filled}{'░' * (width - filled)} {int(ratio * 100)}%"
