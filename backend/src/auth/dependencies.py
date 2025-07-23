"""Authentication dependencies for FastAPI."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from src.auth.manager import AuthUser, auth_manager


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


# This is the dependency that will be used in all router endpoints.
EffectiveUserId = Annotated[UUID, Depends(_get_effective_user_id)]
CurrentUser = Annotated[AuthUser | None, Depends(_get_current_user)]
RequiredUser = Annotated[AuthUser, Depends(_get_required_user)]
CurrentUserId = Annotated[UUID | None, Depends(_get_current_user_id)]
