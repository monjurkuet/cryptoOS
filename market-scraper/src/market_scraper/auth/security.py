"""Password, session-token, and CSRF helpers."""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import UTC, datetime, timedelta

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_PASSWORD_HASHER = PasswordHasher()


def normalize_email(email: str) -> str:
    """Normalize and validate an email address."""
    normalized = email.strip().lower()
    if not EMAIL_RE.match(normalized):
        raise ValueError("Invalid email address")
    return normalized


def hash_password(password: str) -> str:
    """Hash a password with Argon2id."""
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an Argon2id hash."""
    try:
        return bool(_PASSWORD_HASHER.verify(password_hash, password))
    except (InvalidHashError, VerifyMismatchError):
        return False


def new_secret_token() -> str:
    """Create a high-entropy URL-safe token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a session or CSRF token for storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expires_at(ttl_hours: int) -> datetime:
    """Calculate a UTC session expiry timestamp."""
    return datetime.now(UTC) + timedelta(hours=ttl_hours)
