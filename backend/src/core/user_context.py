"""Unified user context management for seamless single/multi-user support."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING
from uuid import UUID

from src.auth.manager import auth_manager
from src.config.settings import DEFAULT_USER_ID, get_settings


if TYPE_CHECKING:
    from fastapi import Request


logger = logging.getLogger(__name__)


@dataclass
class UserContext:
    """Unified user context that works across auth modes."""

    user_id: UUID
    email: str | None = None
    name: str | None = None
    is_authenticated: bool = False
    is_default_user: bool = False
    auth_mode: str = "none"

    @property
    def id_str(self) -> str:
        """Get user ID as string."""
        return str(self.user_id)

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id_str,
            "email": self.email,
            "name": self.name,
            "is_authenticated": self.is_authenticated,
            "auth_mode": self.auth_mode,
        }


class UserContextService:
    """Service for managing user context across different auth modes."""

    @staticmethod
    async def get_user_context(request: "Request") -> UserContext:
        """Get unified user context from request.

        This method provides a consistent interface regardless of auth mode:
        - In single-user mode: Returns default user context
        - In multi-user mode: Returns authenticated user or default

        Args:
            request: FastAPI request object

        Returns
        -------
            UserContext with user information
        """
        settings = get_settings()

        # Try to get authenticated user
        auth_user = await auth_manager.get_current_user(request)

        if auth_user:
            # We have an authenticated user
            return UserContext(
                user_id=auth_user.id,  # auth_user.id is already a UUID
                email=auth_user.email,
                name=auth_user.name,
                is_authenticated=True,
                is_default_user=False,
                auth_mode=settings.AUTH_PROVIDER,
            )

        # No authenticated user - use default
        return UserContext(
            user_id=DEFAULT_USER_ID,
            email="demo@talimio.com",
            name="Demo User",
            is_authenticated=False,
            is_default_user=True,
            auth_mode=settings.AUTH_PROVIDER,
        )

    @staticmethod
    def get_effective_user_id(request: "Request") -> UUID:
        """Get effective user ID from request (sync version for dependencies).

        This is a lightweight sync version that just extracts the ID.

        Args:
            request: FastAPI request object

        Returns
        -------
            User ID (never None)
        """
        return auth_manager.get_effective_user_id(request)

    @staticmethod
    async def require_authenticated_user(request: "Request") -> UserContext:
        """Get user context, requiring authentication.

        Args:
            request: FastAPI request object

        Returns
        -------
            UserContext if authenticated

        Raises
        ------
            HTTPException: 401 if not authenticated
        """
        context = await UserContextService.get_user_context(request)

        if not context.is_authenticated and context.is_default_user:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=401,
                detail="Authentication required"
            )

        return context

    @staticmethod
    def log_context(context: UserContext, action: str) -> None:
        """Log user context for debugging.

        Args:
            context: User context
            action: Action being performed
        """
        logger.info(
            f"User action: {action}",
            extra={
                "user_id": context.id_str,
                "is_authenticated": context.is_authenticated,
                "auth_mode": context.auth_mode,
                "is_default": context.is_default_user,
            }
        )


# FastAPI dependency for user context
async def get_user_context(request: "Request") -> UserContext:
    """FastAPI dependency to get user context."""
    return await UserContextService.get_user_context(request)


# Backward compatibility function
def get_effective_user_id(request: "Request") -> UUID:
    """Get effective user ID from request.

    This is a backward compatibility wrapper for existing code.
    New code should use UserContextService.get_effective_user_id() or
    the EffectiveUserId dependency from auth.dependencies.
    """
    return UserContextService.get_effective_user_id(request)
