"""Security helpers: password hashing for private lobbies and token signing.

Lobby passwords are low-value and short-lived, but we still never store them in
plaintext. We use PBKDF2-HMAC-SHA256 with a per-password random salt.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

_PBKDF2_ROUNDS = 120_000


def hash_password(password: str) -> str:
    """Return ``salt$hash`` (both hex) for a plaintext password."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """Constant-time verification of a password against a stored hash."""
    try:
        salt_hex, digest_hex = stored.split("$", 1)
    except ValueError:
        return False
    salt = bytes.fromhex(salt_hex)
    expected = bytes.fromhex(digest_hex)
    candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return hmac.compare_digest(candidate, expected)
