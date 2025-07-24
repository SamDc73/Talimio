"""Authentication dependencies for FastAPI."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request

from src.auth.manager import AuthUser, auth_manager
from src.config.settings import get_settings
from src.core.user_context import UserContext, get_user_context


def _get_effective_user_id(request: Request) -> UUID:
    """
    FastAPI dependency to get the effective user ID.

    - If auth is enabled and user is logged in, returns their ID.
    - If auth is disabled or no user is logged in, returns DEFAULT_USER_ID.

    This provides a single, reliable source for the user ID for any request.
    """
    return auth_manager.get_effective_user_id(request)


async def _get_current_user(request: Request) -> AuthUser | None:
    """
    FastAPI dependency to get the current authenticated user.

    Returns None if no user is authenticated.
    """
    return await auth_manager.get_current_user(request)


async def _get_required_user(request: Request) -> AuthUser:
    """
    FastAPI dependency to get the current authenticated user.

    Raises HTTPException if no user is authenticated.
    """
    return await auth_manager.get_current_user_required(request)


def _get_current_user_id(request: Request) -> UUID | None:
    """
    FastAPI dependency to get the current user ID.

    Returns None if no user is authenticated.
    """
    return auth_manager.get_user_id(request)


# New mode-aware dependencies (preferred for new code)
async def _get_user_context(request: Request) -> UserContext:
    """Get user context (works in both auth modes)."""
    return await get_user_context(request)


async def _require_auth_in_multi_user_mode(request: Request) -> UserContext:
    """Require authentication only in multi-user mode."""
    settings = get_settings()
    context = await get_user_context(request)

    # In multi-user mode, require actual authentication
    if settings.AUTH_PROVIDER == "supabase" and not context.is_authenticated:
        raise HTTPException(
            status_code=401,
            detail="Authentication required in multi-user mode"
        )

    return context


async def _get_optional_user_context(request: Request) -> UserContext | None:
    """Get user context for truly optional cases."""
    try:
        return await get_user_context(request)
    except Exception:
        return None


# Legacy dependencies (maintained for backward compatibility)
EffectiveUserId = Annotated[UUID, Depends(_get_effective_user_id)]
CurrentUser = Annotated[AuthUser | None, Depends(_get_current_user)]
RequiredUser = Annotated[AuthUser, Depends(_get_required_user)]
CurrentUserId = Annotated[UUID | None, Depends(_get_current_user_id)]

# New mode-aware dependencies (use these for new endpoints)
UserContextDep = Annotated[UserContext, Depends(_get_user_context)]
RequireAuthInMultiUser = Annotated[UserContext, Depends(_require_auth_in_multi_user_mode)]
OptionalUserContext = Annotated[UserContext | None, Depends(_get_optional_user_context)]


# Simple Dependency Injection
async def get_current_user_id(request: Request) -> UUID:
    """
    Single place for ALL auth logic.

    Returns the effective user ID for the current request:
    - In auth mode: Returns authenticated user's ID
    - In non-auth mode: Returns DEFAULT_USER_ID

    This replaces UserContext for simple user_id injection at API boundaries.
    """
    return auth_manager.get_effective_user_id(request)


# Clean dependency injection for user ID
UserId = Annotated[UUID, Depends(get_current_user_id)]
