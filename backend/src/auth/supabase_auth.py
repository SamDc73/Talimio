"""Simplified Supabase authentication using their built-in session management."""

import logging
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, Request
from supabase import Client, ClientOptions, create_client

from src.auth.models import UserInDB
from src.config.settings import get_settings


logger = logging.getLogger(__name__)


class SupabaseAuth:
    """Handle Supabase authentication with built-in session management."""

    def __init__(self) -> None:
        """Initialize Supabase client."""
        settings = get_settings()

        if not settings.SUPABASE_URL or not settings.SUPABASE_PUBLISHABLE_KEY:
            error_msg = "Supabase configuration missing"
            raise ValueError(error_msg)

        # Use publishable key for client-side auth verification
        # Supabase handles token refresh automatically
        options = ClientOptions(
            auto_refresh_token=True,
            persist_session=False,  # Don't persist on server
        )
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_PUBLISHABLE_KEY, options=options)

    async def get_user_from_request(self, request: Request) -> UserInDB | None:
        """Extract and verify user from Supabase JWT in request."""
        # Get token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return None

        token = auth_header.split(" ")[1]

        try:
            # Verify token with Supabase
            # This automatically handles expired tokens
            user_response = self.supabase.auth.get_user(token)

            if not user_response or not user_response.user:
                return None

            user = user_response.user

            return UserInDB(
                id=UUID(str(user.id)),
                email=user.email,
                username=user.user_metadata.get("username"),
                created_at=datetime.fromisoformat(user.created_at),
                metadata=user.user_metadata,
            )
        except Exception:
            logger.exception("Token verification failed")
            return None

    async def require_user(self, request: Request) -> UserInDB:
        """Get user or raise 401."""
        user = await self.get_user_from_request(request)
        if not user:
            raise HTTPException(
                status_code=401,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user
