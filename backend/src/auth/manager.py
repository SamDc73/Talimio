"""Simple authentication layer with no-auth and Supabase support."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID

from src.config.settings import get_settings


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from fastapi import Request


class AuthProviderType(Enum):
    """Supported authentication providers."""

    NONE = "none"  # Self-hosted, no auth
    SUPABASE = "supabase"  # Supabase Auth


@dataclass
class AuthUser:
    """User representation across auth providers."""

    id: str
    email: str | None = None
    name: str | None = None
    metadata: dict | None = None


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @abstractmethod
    async def get_current_user(self, request: "Request") -> AuthUser | None:
        """Get the current authenticated user from the request."""

    @abstractmethod
    def get_user_id(self, request: "Request") -> UUID | None:
        """Get just the user ID from the request (lightweight operation)."""


class NoAuthProvider(AuthProvider):
    """No authentication - single user mode."""

    DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

    async def get_current_user(self, request: "Request") -> AuthUser | None:  # noqa: ARG002
        """Get current user for no-auth mode."""
        return AuthUser(id=str(self.DEFAULT_USER_ID), email="demo@talimio.com", name="Demo User")

    def get_user_id(self, request: "Request") -> UUID | None:  # noqa: ARG002
        """Get user ID for no-auth mode."""
        return self.DEFAULT_USER_ID


class SupabaseAuthProvider(AuthProvider):
    """Supabase authentication provider (2025 API patterns)."""

    def __init__(self) -> None:
        """Initialize Supabase client."""
        from supabase import Client, create_client

        settings = get_settings()

        if not settings.SUPABASE_URL or not settings.SUPABASE_SECRET_KEY:
            msg = "Supabase configuration missing"
            raise ValueError(msg)

        self.supabase: Client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SECRET_KEY
        )

    async def get_current_user(self, request: "Request") -> AuthUser | None:
        """Extract and verify Supabase JWT token."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            # Use Supabase's get_user method (2025 pattern)
            user_response = await self.supabase.auth.get_user(token)
            if not user_response or not user_response.user:
                return None

            return AuthUser(
                id=str(user_response.user.id),
                email=user_response.user.email,
                name=user_response.user.user_metadata.get("username"),
                metadata=user_response.user.user_metadata
            )
        except Exception:
            return None

    def get_user_id(self, request: "Request") -> UUID | None:
        """Lightweight user ID extraction from Supabase JWT."""
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            logger.debug("No Authorization header or invalid format")
            return None

        token = auth_header.split(" ")[1]

        try:
            # Decode JWT to get user ID without full verification
            import jwt
            # Decode without verification for quick ID extraction
            payload = jwt.decode(token, options={"verify_signature": False})
            user_id = payload.get("sub")  # 'sub' contains user ID in Supabase JWTs
            if user_id:
                logger.debug(f"Extracted user ID from JWT: {user_id}")
                return UUID(user_id)
            logger.warning("JWT payload does not contain 'sub' field")
            return None
        except Exception as e:
            logger.error(f"Failed to decode JWT token: {e}")
            return None


class AuthManager:
    """Main authentication manager that delegates to the configured provider."""

    def __init__(self) -> None:
        self.provider = self._get_auth_provider()

    def _get_auth_provider(self) -> AuthProvider:
        """Get the configured authentication provider."""
        settings = get_settings()
        auth_provider = getattr(settings, "AUTH_PROVIDER", "none").lower()

        if auth_provider == "none" or getattr(settings, "AUTH_DISABLED", False):
            return NoAuthProvider()
        if auth_provider == "supabase":
            return SupabaseAuthProvider()

        error_msg = f"Unsupported auth provider: {auth_provider}. Use 'none' or 'supabase'"
        raise ValueError(error_msg)

    async def get_current_user(self, request: "Request") -> AuthUser | None:
        """Get the current authenticated user."""
        return await self.provider.get_current_user(request)

    def get_user_id(self, request: "Request") -> UUID | None:
        """Get the current user ID (lightweight)."""
        return self.provider.get_user_id(request)

    def get_effective_user_id(self, request: "Request") -> UUID:
        """Get effective user ID, never None. Includes error boundaries."""
        try:
            user_id = self.get_user_id(request)
            if user_id is None:
                # Fallback to default user ID
                logger.info("No user ID found in request, using default user ID")
                return NoAuthProvider.DEFAULT_USER_ID
            logger.debug(f"Using authenticated user ID: {user_id}")
            return user_id
        except Exception as e:
            # Always fallback to default user ID on any auth failure
            logger.error(f"Error getting user ID, falling back to default: {e}")
            return NoAuthProvider.DEFAULT_USER_ID

    async def get_current_user_required(self, request: "Request") -> AuthUser:
        """Get current user or raise 401 if not authenticated."""
        user = await self.get_current_user(request)
        if not user:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Not authenticated")
        return user


# Global auth manager instance
auth_manager = AuthManager()
