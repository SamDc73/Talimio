"""Simplified auth routes that leverage Supabase's built-in session management."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from src.auth.supabase_auth import SupabaseAuth


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

# Initialize Supabase auth
supabase_auth = SupabaseAuth()


class UserResponse(BaseModel):
    """User response model."""

    id: str
    email: str
    username: str | None = None


@router.get("/me")
async def get_current_user(request: Request) -> UserResponse:
    """
    Get current user from Supabase token.

    The frontend handles token refresh automatically via @supabase/ssr.
    """
    user = await supabase_auth.require_user(request)

    return UserResponse(id=str(user.id), email=user.email or "", username=user.username)


@router.get("/verify")
async def verify_token(request: Request) -> dict:
    """Verify if the current token is valid."""
    user = await supabase_auth.get_user_from_request(request)

    return {"valid": user is not None, "user_id": str(user.id) if user else None}


# Note: Login, signup, logout, and token refresh are handled entirely
# by Supabase on the frontend using @supabase/ssr
# The backend only needs to verify tokens for protected endpoints
