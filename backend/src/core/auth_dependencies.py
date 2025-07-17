"""FastAPI dependencies for authentication."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from .auth_manager import AuthUser, auth_manager


async def get_current_user(request: Request) -> AuthUser | None:
    """Get the current authenticated user (can be None)."""
    return await auth_manager.get_current_user(request)


async def get_current_user_id(request: Request) -> str | None:
    """Get the current user ID (lightweight, can be None)."""
    return auth_manager.get_user_id(request)


async def get_effective_user_id(request: Request) -> UUID:
    """Get effective user ID (never None, handles single-user mode)."""
    return auth_manager.get_effective_user_id(request)


# Type aliases for easier usage
CurrentUser = Annotated[AuthUser | None, Depends(get_current_user)]
CurrentUserId = Annotated[str | None, Depends(get_current_user_id)]
EffectiveUserId = Annotated[str, Depends(get_effective_user_id)]
