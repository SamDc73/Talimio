"""Core authentication configuration, schemes, and dependencies.

Provide cookie scheme definition, JWT token decoding, user ID resolution,
and FastAPI dependency injection for authentication.
"""

import logging
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie

from src.auth.exceptions import (
    InvalidTokenError,
    TokenExpiredError,
)
from src.auth.security import get_jwt_signing_key
from src.config.settings import get_settings


logger = logging.getLogger(__name__)

# THE ONLY USER ID CONSTANT IN THE ENTIRE CODEBASE
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

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

    user_id: UUID
    token_version: int
    session_id: UUID | None


def get_local_token_version_from_state(request: Request) -> int | None:
    """Read local token version from request state."""
    token_version = getattr(request.state, "local_token_version", None)
    if isinstance(token_version, int) and not isinstance(token_version, bool):
        return token_version
    return None


def get_local_session_id_from_state(request: Request) -> UUID | None:
    """Read local auth session ID from request state."""
    session_id = getattr(request.state, "local_session_id", None)
    if isinstance(session_id, UUID):
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


def _parse_session_id(payload: dict[str, object]) -> UUID | None:
    """Parse and validate auth session ID claim."""
    raw_session_id = payload.get("sid")
    if raw_session_id is None:
        return None
    if isinstance(raw_session_id, str):
        try:
            return UUID(raw_session_id)
        except ValueError as error:
            raise InvalidTokenError from error
    raise InvalidTokenError


def _parse_user_id(payload: dict[str, object]) -> UUID:
    """Parse and validate user ID subject claim."""
    try:
        return UUID(str(payload["sub"]))
    except (ValueError, TypeError, KeyError) as error:
        raise InvalidTokenError from error


def decode_local_token_claims(token: str, *, jwt_secret: str) -> LocalTokenClaims:
    """Decode and validate local auth JWT claims."""
    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError as error:
        raise TokenExpiredError from error
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
    except (InvalidTokenError, TokenExpiredError):
        return None


def _store_local_claims_on_request(request: Request, claims: LocalTokenClaims) -> None:
    """Store validated local token metadata on request state."""
    request.state.local_token_version = claims.token_version
    request.state.local_session_id = claims.session_id


# ---------------------------------------------------------------------------
# User ID resolution
# ---------------------------------------------------------------------------
async def get_user_id(request: Request, token: str) -> UUID:
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


def _get_single_user_mode_id() -> UUID:
    """Return the default user ID in single-user mode."""
    return DEFAULT_USER_ID


def _get_local_user_id(request: Request, *, token: str, jwt_secret: str) -> UUID:
    """Resolve authenticated user ID from local JWT cookie."""
    claims = decode_local_token_claims(token, jwt_secret=jwt_secret)
    _store_local_claims_on_request(request, claims)
    return claims.user_id


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
async def _get_user_id_dependency(
    request: Request,
    auth_token: CookieToken,
) -> UUID:
    """Get user ID dependency for FastAPI routes.

    Thin wrapper around get_user_id() for use as a FastAPI dependency.
    Token extraction is handled exclusively by FastAPI DI via CookieToken.
    """
    settings = get_settings()
    if settings.AUTH_PROVIDER == "local" and not auth_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user_id = await get_user_id(request, token=auth_token or "")
    request.state.user_id = user_id
    return user_id
