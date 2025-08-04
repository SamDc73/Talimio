"""Authentication routes for user login, signup, and session management."""

import contextlib
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from src.auth.config import DEFAULT_USER_ID, get_user_id, supabase
from src.config.settings import get_settings
from src.middleware.security import auth_rate_limit


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly auth cookie (secure!)."""
    settings = get_settings()
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,  # Can't be accessed by JS (XSS protection)
        secure=settings.ENVIRONMENT == "production",  # HTTPS only in prod
        samesite="lax",  # CSRF protection
        max_age=24 * 60 * 60,  # 24 hours
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear auth cookie on logout."""
    settings = get_settings()
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",  # Match set_auth_cookie logic
        samesite="lax",
    )


class LoginRequest(BaseModel):
    """Login request model."""

    email: EmailStr
    password: str


class SignupRequest(BaseModel):
    """Signup request model."""

    email: EmailStr
    password: str
    username: str | None = None


class AuthResponse(BaseModel):
    """Auth response model."""

    user: dict
    access_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int


class SignupResponse(BaseModel):
    """Signup response model - can handle both immediate auth and email confirmation."""

    user: dict
    access_token: str | None = None
    token_type: str = "bearer"  # noqa: S105
    expires_in: int | None = None
    email_confirmation_required: bool = False
    message: str | None = None


class UserResponse(BaseModel):
    """User response model."""

    id: str
    email: str
    username: str | None = None


class PasswordResetRequest(BaseModel):
    """Password reset request model."""

    email: EmailStr


# Removed get_supabase_client() - now using shared client from config.py


@router.post("/signup")
@auth_rate_limit
async def signup(request: Request, data: SignupRequest) -> SignupResponse:  # noqa: ARG001
    """Create a new user account."""
    settings = get_settings()

    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(status_code=400, detail="Signup is only available with Supabase authentication")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Create user with Supabase Auth
        auth_response = supabase.auth.sign_up(
            {
                "email": data.email,
                "password": data.password,
                "options": {"data": {"username": data.username or data.email.split("@")[0]}},
            }
        )

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")

        # If email confirmation is enabled, session will be None
        if not auth_response.session:
            # Return a special response indicating email confirmation is needed
            return SignupResponse(
                user={
                    "id": str(auth_response.user.id),
                    "email": auth_response.user.email,
                    "username": auth_response.user.user_metadata.get("username"),
                },
                message="Please check your email to confirm your account",
                email_confirmation_required=True,
            )

        return SignupResponse(
            user={
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": auth_response.user.user_metadata.get("username"),
            },
            access_token=auth_response.session.access_token,
            expires_in=auth_response.session.expires_in,
            email_confirmation_required=False,
        )

    except Exception as e:
        # If it's a Supabase auth error, try to get more details
        error_detail = str(e)
        if hasattr(e, "message"):
            error_detail = e.message  # type: ignore[attr-defined]
        elif hasattr(e, "args") and e.args:
            error_detail = str(e.args[0])

        raise HTTPException(status_code=400, detail=error_detail) from e


@router.post("/login")
@auth_rate_limit
async def login(request: Request, response: Response, data: LoginRequest) -> dict:  # noqa: ARG001
    """Login with email and password."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(status_code=400, detail="Login is only available with Supabase authentication")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({"email": data.email, "password": data.password})

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Set secure httpOnly cookies for both access and refresh tokens
        set_auth_cookie(response, auth_response.session.access_token)

        # Also set refresh token cookie
        response.set_cookie(
            key="refresh_token",
            value=auth_response.session.refresh_token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )

        return {
            "user": {
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": auth_response.user.user_metadata.get("username"),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials") from e


@router.post("/logout")
async def logout(_request: Request, response: Response) -> dict[str, str]:
    """Logout the current user."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        return {"message": "Logout not required in current auth mode"}

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Clear both httpOnly cookies (this is the real logout)
    clear_auth_cookie(response)
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=settings.ENVIRONMENT == "production",  # Consistent with other cookies
        samesite="lax",
    )

    with contextlib.suppress(Exception):
        # Try to sign out with Supabase (optional)
        supabase.auth.sign_out()

    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user(request: Request) -> UserResponse:
    """Get the current user (authenticated in multi-user mode, default in single-user mode)."""
    user_id = await get_user_id(request)
    settings = get_settings()

    # In single-user mode, return default user (FIXED: check for "none" not "single_user")
    if settings.AUTH_PROVIDER == "none" or user_id == DEFAULT_USER_ID:
        return UserResponse(
            id=str(DEFAULT_USER_ID),
            email="demo@talimio.com",
            username="Demo User"
        )

    # In multi-user mode, get user from Supabase
    if supabase:
        # Try Authorization header first
        auth_header = request.headers.get("Authorization", "")
        token = None

        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
        else:
            # Check for token in cookies (for httpOnly cookie auth)
            cookie_token = request.cookies.get("access_token")
            if cookie_token:
                # Strip "Bearer " prefix if present
                token = cookie_token.replace("Bearer ", "") if cookie_token.startswith("Bearer ") else cookie_token

        if token:
            try:
                # Supabase SDK expects just the token, not "Bearer " + token
                user = supabase.auth.get_user(token)
                if user and user.user:
                    return UserResponse(
                        id=str(user.user.id),
                        email=user.user.email,
                        username=user.user.user_metadata.get("username", user.user.email.split("@")[0])
                    )
            except Exception:
                logger.warning("Failed to get user info from token")

    # Fallback to default user
    return UserResponse(
        id=str(DEFAULT_USER_ID),
        email="demo@talimio.com",
        username="Demo User"
    )


@router.post("/refresh")
async def refresh_token(request: Request, response: Response) -> dict:
    """Refresh the access token using the refresh_token cookie."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(status_code=400, detail="Token refresh is only available with Supabase authentication")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Get refresh token from cookie
        refresh_token_value = request.cookies.get("refresh_token")
        if not refresh_token_value:
            raise HTTPException(status_code=401, detail="No refresh token provided")

        # Use the refresh token to get a new session
        # The correct Supabase method expects the refresh_token as a parameter
        auth_response = supabase.auth.refresh_session(refresh_token_value)

        if not auth_response or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Update both access and refresh tokens in cookies
        set_auth_cookie(response, auth_response.session.access_token)

        # Also update the refresh token cookie with the new one
        response.set_cookie(
            key="refresh_token",
            value=auth_response.session.refresh_token,
            httponly=True,
            secure=settings.ENVIRONMENT == "production",
            samesite="lax",
            max_age=7 * 24 * 60 * 60,  # 7 days
        )

        return {
            "message": "Token refreshed successfully",
            "user": {
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": auth_response.user.user_metadata.get("username"),
            },
        }

    except Exception as e:
        # Log the actual error for debugging
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Token refresh failed")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token") from e


@router.post("/reset-password")
@auth_rate_limit
async def reset_password(request: Request, data: PasswordResetRequest) -> dict[str, str]:  # noqa: ARG001
    """Send password reset email via Supabase Auth."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(
            status_code=400,
            detail="Password reset is only available with Supabase authentication"
        )

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Use Supabase's built-in password reset
        # According to the docs, it's resetPasswordForEmail in JS but Python uses snake_case
        supabase.auth.reset_password_email(data.email)
        # Don't reveal if email exists or not for security
        return {"message": "If the email exists, password reset instructions have been sent"}
    except Exception:
        # Always return the same message for security (don't reveal if email exists)
        return {"message": "If the email exists, password reset instructions have been sent"}


# Debug endpoint to verify authentication
@router.get("/debug")
async def debug_auth(request: Request) -> dict:
    """Debug endpoint to check authentication status."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization")
    user_id = await get_user_id(request)

    # Try to get current user info if available
    current_user_info = None
    if supabase and auth_header and auth_header.startswith("Bearer "):
        try:
            # Extract token properly (remove "Bearer " prefix)
            token = auth_header.replace("Bearer ", "")
            # Supabase SDK expects just the token, not "Bearer " + token
            user = supabase.auth.get_user(token)
            if user and user.user:
                current_user_info = {
                    "id": str(user.user.id),
                    "email": user.user.email,
                    "username": user.user.user_metadata.get("username")
                }
        except Exception:
            logger.warning("Failed to get debug user info from token")

    return {
        "auth_provider": settings.AUTH_PROVIDER,
        "has_auth_header": bool(auth_header),
        "auth_header_preview": auth_header[:50] + "..." if auth_header and len(auth_header) > 50 else auth_header,
        "effective_user_id": str(user_id),
        "current_user": current_user_info,
        "is_default_user": user_id == DEFAULT_USER_ID,
    }
