"""Ultra-simple auth configuration - ONE place for EVERYTHING."""

import logging
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from supabase import create_client

from src.auth.exceptions import (
    InvalidTokenError,
    MissingTokenError,
    SupabaseConfigError,
    UnknownAuthProviderError,
)
from src.config.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()

# THE ONLY USER ID CONSTANT IN THE ENTIRE CODEBASE
DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

# Initialize Supabase client ONCE
supabase = (
    create_client(settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY)
    if settings.AUTH_PROVIDER == "supabase" and settings.SUPABASE_URL
    else None
)


def _extract_token_from_request(request: Request) -> str | None:
    """Extract JWT token from request headers or cookies."""
    # First check Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.replace("Bearer ", "")

    # Check for token in cookies (for httpOnly cookie auth)
    cookie_token = request.cookies.get("access_token")
    if cookie_token:
        # Strip "Bearer " prefix if present (set_auth_cookie adds it)
        return cookie_token.replace("Bearer ", "") if cookie_token.startswith("Bearer ") else cookie_token

    return None


def _validate_supabase_token(token: str) -> UUID:
    """Validate Supabase token and return user ID."""
    try:
        # Supabase SDK expects just the token, not "Bearer " + token
        response = supabase.auth.get_user(token)
        if response.user and response.user.id:
            user_id = UUID(response.user.id)
            logger.debug(f"Successfully authenticated user: {user_id}")
            return user_id
        logger.warning("Token validation returned no user")
        raise InvalidTokenError
    except InvalidTokenError:
        # Re-raise our custom exceptions
        raise
    except Exception as e:
        # SECURITY FIX: In multi-user mode, NEVER fall back to DEFAULT_USER_ID
        # Invalid tokens must be REJECTED, not given default access
        logger.exception("Token validation failed: %s", e)
        raise InvalidTokenError from e


async def get_user_id(request: Request) -> UUID:
    """
    RADICALLY SIMPLE user ID resolution with PROPER security.

    Single-user mode: Always returns DEFAULT_USER_ID.
    Multi-user mode: VALIDATES Supabase token or REJECTS request.
    """
    # Single-user mode - always the same ID (FIXED: check for "none" not "single_user")
    if settings.AUTH_PROVIDER == "none":
        return DEFAULT_USER_ID

    # Multi-user mode - STRICT validation, NO fallback to default
    if settings.AUTH_PROVIDER == "supabase":
        if not supabase:
            logger.error("Supabase client not initialized for multi-user mode")
            raise SupabaseConfigError

        token = _extract_token_from_request(request)
        if not token:
            logger.warning("Missing or invalid Authorization header and no access_token cookie")
            raise MissingTokenError

        return _validate_supabase_token(token)

    # Unknown auth provider
    logger.error(f"Unknown auth provider: {settings.AUTH_PROVIDER}")
    raise UnknownAuthProviderError(settings.AUTH_PROVIDER)


# FastAPI Dependency - The ONLY auth dependency in the entire codebase
async def _get_user_id(request: Request) -> UUID:
    """Get user ID dependency for FastAPI routes."""
    # Check if middleware already set the user_id
    if hasattr(request.state, "user_id") and request.state.user_id is not None:
        return request.state.user_id
    # Otherwise, get it directly
    return await get_user_id(request)


# This is the dependency to use in routers
UserId = Annotated[UUID, Depends(_get_user_id)]
