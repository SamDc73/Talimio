
"""Core authentication configuration, schemes, and dependencies.

Provide cookie scheme definition, JWT token decoding, user ID resolution,
and FastAPI dependency injection for authentication.
"""

import logging
import uuid
from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie

from src.auth.config import DEFAULT_USER_ID
from src.auth.exceptions import (
    InvalidTokenError,
)
from src.auth.security import get_jwt_signing_key
from src.config.settings import get_settings


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cookie scheme
# ---------------------------------------------------------------------------
_settings = get_settings()

# auto_error=False so protected dependencies can return 401 (not 403) with a controlled message.
_cookie_scheme = APIKeyCookie(
    name=_settings.AUTH_COOKIE_NAME,
    scheme_name="AuthCookie",
    auto_error=False,
)

# Type aliases for FastAPI dependency injection.
CookieToken = Annotated[str | None, Security(_cookie_scheme)]
CookieTokenOptional = Annotated[str | None, Security(_cookie_scheme)]


# ---------------------------------------------------------------------------
# Local JWT token claims
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LocalTokenClaims:
    """Validated local JWT claims used by request auth flows."""

    user_id: uuid.UUID
    token_version: int
    session_id: uuid.UUID | None


def get_local_token_version_from_state(request: Request) -> int | None:
    """Read local token version from request state."""
    token_version = getattr(request.state, "local_token_version", None)
    if isinstance(token_version, int) and not isinstance(token_version, bool):
        return token_version
    return None


def get_local_session_id_from_state(request: Request) -> uuid.UUID | None:
    """Read local auth session ID from request state."""
    session_id = getattr(request.state, "local_session_id", None)
    if isinstance(session_id, uuid.UUID):
        return session_id
    return None


def _parse_token_version(payload: dict[str, object]) -> int:
    """Parse and validate token version claim."""
    raw_token_version = payload.get("ver", 0)
    if isinstance(raw_token_version, bool):
        raise InvalidTokenError
    if isinstance(raw_token_version, int):
        return raw_token_version
    if isinstance(raw_token_version, str):
        try:
            return int(raw_token_version)
        except ValueError as error:
            raise InvalidTokenError from error
    raise InvalidTokenError


def _parse_session_id(payload: dict[str, object]) -> uuid.UUID | None:
    """Parse and validate auth session ID claim."""
    raw_session_id = payload.get("sid")
    if raw_session_id is None:
        return None
    if isinstance(raw_session_id, str):
        try:
            return uuid.UUID(raw_session_id)
        except ValueError as error:
            raise InvalidTokenError from error
    raise InvalidTokenError


def _parse_user_id(payload: dict[str, object]) -> uuid.UUID:
    """Parse and validate user ID subject claim."""
    try:
        return uuid.UUID(str(payload["sub"]))
    except (ValueError, TypeError, KeyError) as error:
        raise InvalidTokenError from error


def decode_local_token_claims(token: str, *, jwt_secret: str) -> LocalTokenClaims:
    """Decode and validate local auth JWT claims."""
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError as error:
        raise InvalidTokenError from error

    if not isinstance(payload, dict):
        raise InvalidTokenError

    return LocalTokenClaims(
        user_id=_parse_user_id(payload),
        token_version=_parse_token_version(payload),
        session_id=_parse_session_id(payload),
    )


def decode_local_token_claims_optional(token: str | None, *, jwt_secret: str) -> LocalTokenClaims | None:
    """Decode local auth JWT claims for best-effort flows (e.g., logout)."""
    if not token:
        return None
    try:
        return decode_local_token_claims(token, jwt_secret=jwt_secret)
    except InvalidTokenError:
        return None


def _store_local_claims_on_request(request: Request, claims: LocalTokenClaims) -> None:
    """Store validated local token metadata on request state."""
    request.state.local_token_version = claims.token_version
    request.state.local_session_id = claims.session_id


# ---------------------------------------------------------------------------
# User ID resolution
# ---------------------------------------------------------------------------
def get_user_id(request: Request, token: str) -> uuid.UUID:
    """Resolve authenticated user ID.

    Single-user mode: always return DEFAULT_USER_ID.
    Local mode: validate local JWT token or reject request.
    """
    settings = get_settings()
    if settings.AUTH_PROVIDER == "none":
        return _get_single_user_mode_id()
    if settings.AUTH_PROVIDER == "local":
        return _get_local_user_id(request, token=token, jwt_secret=get_jwt_signing_key())

    logger.error("Unknown auth provider: %s", settings.AUTH_PROVIDER)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication provider is not supported",
    )


def _get_single_user_mode_id() -> uuid.UUID:
    """Return the default user ID in single-user mode."""
    return DEFAULT_USER_ID


def _get_local_user_id(request: Request, *, token: str, jwt_secret: str) -> uuid.UUID:
    """Resolve authenticated user ID from local JWT cookie."""
    claims = decode_local_token_claims(token, jwt_secret=jwt_secret)
    _store_local_claims_on_request(request, claims)
    return claims.user_id


def _get_local_auth_token(request: Request, cookie_token: str | None) -> str | None:
    """Resolve local auth token from cookie first, then bearer auth header."""
    if cookie_token:
        return cookie_token

    authorization = request.headers.get("authorization", "")
    scheme, _, credentials = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return None

    token = credentials.strip()
    if not token:
        return None

    return token


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def _get_user_id_dependency(
    request: Request,
    auth_token: CookieToken,
) -> uuid.UUID:
    """Get user ID dependency for FastAPI routes.

    Thin wrapper around get_user_id() for use as a FastAPI dependency.
    Token extraction is handled exclusively by FastAPI DI via CookieToken.
    """
    settings = get_settings()
    resolved_token = auth_token
    if settings.AUTH_PROVIDER == "local":
        resolved_token = _get_local_auth_token(request, auth_token)
        if not resolved_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = get_user_id(request, token=resolved_token or "")
    request.state.user_id = user_id
    return user_id
