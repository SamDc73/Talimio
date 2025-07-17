"""Abstract authentication layer for multiple auth providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from uuid import UUID

from src.config.settings import get_settings


class AuthProvider(Enum):
    """Supported authentication providers."""

    NONE = "none"  # Self-hosted, no auth
    CLERK = "clerk"  # Clerk.dev
    AUTH0 = "auth0"  # Auth0
    SUPABASE = "supabase"  # Supabase Auth
    CUSTOM_JWT = "jwt"  # Custom JWT implementation


@dataclass
class AuthUser:
    """Normalized user representation across all auth providers."""

    id: str
    email: str | None = None
    name: str | None = None
    metadata: dict | None = None


class AuthProvider(ABC):
    """Abstract base class for authentication providers."""

    @abstractmethod
    async def get_current_user(self, request) -> AuthUser | None:
        """Get the current authenticated user from the request."""

    @abstractmethod
    def get_user_id(self, request) -> str | None:
        """Get just the user ID from the request (lightweight operation)."""


class NoAuthProvider(AuthProvider):
    """No authentication - single user mode."""

    DEFAULT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

    async def get_current_user(self, request) -> AuthUser | None:
        return AuthUser(id=str(self.DEFAULT_USER_ID), email="demo@talimio.com", name="Demo User")

    def get_user_id(self, request) -> str | None:
        return str(self.DEFAULT_USER_ID)


class ClerkAuthProvider(AuthProvider):
    """Clerk.dev authentication provider."""

    async def get_current_user(self, request) -> AuthUser | None:
        # Extract JWT from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        # Verify with Clerk's API or JWT verification
        # Implementation depends on Clerk's Python SDK
        try:
            # TODO: Implement Clerk token verification
            # user_data = await verify_clerk_token(token)
            # return AuthUser(
            #     id=user_data["sub"],
            #     email=user_data.get("email"),
            #     name=user_data.get("name")
            # )
            pass
        except Exception:
            return None

    def get_user_id(self, request) -> str | None:
        # Lightweight version - just extract user ID from token
        # without full verification for performance
        try:
            # TODO: Implement lightweight user ID extraction
            pass
        except Exception:
            return None


class Auth0AuthProvider(AuthProvider):
    """Auth0 authentication provider."""

    async def get_current_user(self, request) -> AuthUser | None:
        # Similar to Clerk but with Auth0's verification
        # TODO: Implement Auth0 verification
        pass

    def get_user_id(self, request) -> str | None:
        # TODO: Implement Auth0 user ID extraction
        pass


class CustomJWTAuthProvider(AuthProvider):
    """Custom JWT authentication (current implementation)."""

    async def get_current_user(self, request) -> AuthUser | None:
        # Use existing JWT verification logic
        # TODO: Adapt current auth system
        pass

    def get_user_id(self, request) -> str | None:
        # TODO: Adapt current auth system
        pass


class AuthManager:
    """Main authentication manager that delegates to the configured provider."""

    def __init__(self):
        self.provider = self._get_auth_provider()

    def _get_auth_provider(self) -> AuthProvider:
        """Get the configured authentication provider."""
        settings = get_settings()

        # Check environment variable or config
        auth_provider = getattr(settings, "AUTH_PROVIDER", "none").lower()

        if auth_provider == "none" or getattr(settings, "AUTH_DISABLED", False):
            return NoAuthProvider()
        if auth_provider == "clerk":
            return ClerkAuthProvider()
        if auth_provider == "auth0":
            return Auth0AuthProvider()
        if auth_provider == "jwt":
            return CustomJWTAuthProvider()
        raise ValueError(f"Unsupported auth provider: {auth_provider}")

    async def get_current_user(self, request) -> AuthUser | None:
        """Get the current authenticated user."""
        return await self.provider.get_current_user(request)

    def get_user_id(self, request) -> str | None:
        """Get the current user ID (lightweight)."""
        return self.provider.get_user_id(request)

    def get_effective_user_id(self, request) -> UUID:
        """Get effective user ID, never None."""
        user_id = self.get_user_id(request)
        if user_id is None:
            if isinstance(self.provider, NoAuthProvider):
                return NoAuthProvider.DEFAULT_USER_ID
            raise ValueError("Authentication required but no user found")
        return UUID(user_id)


# Global auth manager instance
auth_manager = AuthManager()
