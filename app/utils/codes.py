"""Short human-friendly code generation for lobbies and clans."""

from __future__ import annotations

import secrets

# Excludes ambiguous characters (0/O, 1/I/L) for readability when typed.
_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_code(length: int = 6) -> str:
    """Generate a random uppercase alphanumeric code."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
