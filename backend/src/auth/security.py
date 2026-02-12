"""Security primitives for local auth (password hashing + JWT)."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from pwdlib import PasswordHash
from pwdlib.hashers.argon2 import Argon2Hasher

from src.config.settings import get_settings


password_hash = PasswordHash((Argon2Hasher(),))
ALGORITHM = "HS256"
_JWT_KEY_PURPOSE = "jwt"
_SESSION_KEY_PURPOSE = "session"
_CSRF_KEY_PURPOSE = "csrf"


def _derive_secret_key(secret_key: str, purpose: str) -> str:
    """Derive deterministic sub-keys for auth contexts from a shared secret."""
    return hmac.new(secret_key.encode("utf-8"), purpose.encode("utf-8"), hashlib.sha256).hexdigest()


def get_jwt_signing_key() -> str:
    """Return JWT signing key derived from AUTH_SECRET_KEY."""
    secret_key = get_settings().AUTH_SECRET_KEY.get_secret_value()
    return _derive_secret_key(secret_key, _JWT_KEY_PURPOSE)


def get_session_signing_key() -> str:
    """Return session middleware key derived from AUTH_SECRET_KEY."""
    secret_key = get_settings().AUTH_SECRET_KEY.get_secret_value()
    return _derive_secret_key(secret_key, _SESSION_KEY_PURPOSE)


def get_csrf_signing_key() -> str:
    """Return CSRF middleware key derived from AUTH_SECRET_KEY."""
    secret_key = get_settings().AUTH_SECRET_KEY.get_secret_value()
    return _derive_secret_key(secret_key, _CSRF_KEY_PURPOSE)


def create_access_token(
    subject: str | Any,
    expires_delta: timedelta,
    *,
    token_version: int = 0,
    session_id: str | Any | None = None,
) -> str:
    """Create a signed JWT access token for cookie transport."""
    now = datetime.now(UTC)
    expire = now + expires_delta
    to_encode = {"exp": expire, "iat": now, "nbf": now, "sub": str(subject), "ver": token_version}
    if session_id is not None:
        to_encode["sid"] = str(session_id)
    return jwt.encode(to_encode, get_jwt_signing_key(), algorithm=ALGORITHM)


def verify_password(plain: str, hashed: str) -> tuple[bool, str | None]:
    """Verify password and return (verified, updated_hash_if_any)."""
    return password_hash.verify_and_update(plain, hashed)


def get_password_hash(password: str) -> str:
    """Hash password for storage."""
    return password_hash.hash(password)
