"""FastAPI authentication dependencies.

This module provides dependency injection for authentication in FastAPI routes.
The core authentication logic remains in config.py, while this module wraps it
for use as FastAPI dependencies.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from src.auth.config import get_user_id


async def _get_user_id(request: Request) -> UUID:
    """Get user ID dependency for FastAPI routes.

    This is a thin wrapper around get_user_id() that can be used
    as a FastAPI dependency. It checks if the middleware has already
    set the user_id on the request state to avoid duplicate validation.

    Args:
        request: The FastAPI request object

    Returns
    -------
        UUID: The authenticated user's ID or DEFAULT_USER_ID in single-user mode
    """
    # Check if middleware already set the user_id
    if hasattr(request.state, "user_id") and request.state.user_id is not None:
        return request.state.user_id
    # Otherwise, get it directly
    return await get_user_id(request)


# This is the dependency to use in routers
# Usage: async def my_route(user_id: UserId) -> Response:
UserId = Annotated[UUID, Depends(_get_user_id)]
