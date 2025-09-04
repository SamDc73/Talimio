"""Authentication routes for user login, signup, and session management."""

import asyncio
import contextlib
import hashlib
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr

from src.auth.config import DEFAULT_USER_ID, supabase
from src.auth.dependencies import UserId
from src.config.settings import get_settings
from src.middleware.security import api_rate_limit, auth_rate_limit


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
logger = logging.getLogger(__name__)

# Simple in-memory lock for refresh tokens to prevent race conditions
# Maps token prefix to a lock to prevent concurrent refreshes
refresh_locks: dict[str, asyncio.Lock] = {}


async def cleanup_refresh_locks() -> None:
    """Periodically clean up old locks to prevent memory leaks."""
    # Keep only the last 100 locks (most recent refresh attempts)
    if len(refresh_locks) > 100:
        # Clear all locks - they're short-lived anyway
        refresh_locks.clear()
        logger.info("Cleared refresh locks cache")


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly auth cookie (secure!)."""
    settings = get_settings()
    # In development, don't use samesite restrictions for proxy compatibility
    is_production = settings.ENVIRONMENT == "production"
    response.set_cookie(
        key="access_token",
        value=f"Bearer {token}",
        httponly=True,  # Can't be accessed by JS (XSS protection)
        secure=is_production,  # HTTPS only in prod
        samesite="lax" if is_production else None,  # No samesite restriction in dev for proxy
        max_age=24 * 60 * 60,  # 24 hours
        path="/",  # Ensure cookie is available for all paths
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear auth cookie on logout."""
    settings = get_settings()
    is_production = settings.ENVIRONMENT == "production"
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=is_production,  # Match set_auth_cookie logic
        samesite="lax" if is_production else None,
        path="/",
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


class SignupResponse(BaseModel):
    """Signup response model - can handle both immediate auth and email confirmation."""

    user: dict
    access_token: str | None = None
    expires_in: int | None = None
    message: str | None = None
    email_confirmation_required: bool = False


class UserResponse(BaseModel):
    """User response model."""

    id: str
    email: str
    username: str | None = None


class LoginResponse(BaseModel):
    """Login response model."""

    user: UserResponse


class LogoutResponse(BaseModel):
    """Logout response model."""

    message: str


class RefreshResponse(BaseModel):
    """Token refresh response model."""

    message: str
    user: UserResponse


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str


class PasswordResetRequest(BaseModel):
    """Password reset request model."""

    email: EmailStr




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
        # Create user with Supabase Auth (run in thread pool to avoid blocking)
        auth_response = await run_in_threadpool(
            supabase.auth.sign_up,
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
async def login(request: Request, response: Response, data: LoginRequest) -> LoginResponse:  # noqa: ARG001
    """Login with email and password."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(status_code=400, detail="Login is only available with Supabase authentication")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Authenticate with Supabase (run in thread pool to avoid blocking)
        auth_response = await run_in_threadpool(
            supabase.auth.sign_in_with_password,
            {"email": data.email, "password": data.password}
        )

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Set secure httpOnly cookies for both access and refresh tokens
        set_auth_cookie(response, auth_response.session.access_token)

        # Also set refresh token cookie
        is_production = settings.ENVIRONMENT == "production"
        response.set_cookie(
            key="refresh_token",
            value=auth_response.session.refresh_token,
            httponly=True,
            secure=is_production,
            samesite="lax" if is_production else None,
            max_age=7 * 24 * 60 * 60,  # 7 days
            path="/",
        )

        return LoginResponse(
            user=UserResponse(
                id=str(auth_response.user.id),
                email=auth_response.user.email,
                username=auth_response.user.user_metadata.get("username"),
            )
        )

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials") from e


@router.post("/logout")
async def logout(_request: Request, response: Response) -> LogoutResponse:
    """Logout the current user."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        return LogoutResponse(message="Logout not required in current auth mode")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Clear both httpOnly cookies (this is the real logout)
    clear_auth_cookie(response)
    is_production = settings.ENVIRONMENT == "production"
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=is_production,  # Consistent with other cookies
        samesite="lax" if is_production else None,
        path="/",
    )

    with contextlib.suppress(Exception):
        # Try to sign out with Supabase (optional, run in thread pool)
        await run_in_threadpool(supabase.auth.sign_out)

    return LogoutResponse(message="Successfully logged out")


@router.get("/me")
@api_rate_limit  # Add rate limiting to prevent abuse
async def get_current_user(request: Request, user_id: UserId) -> UserResponse:
    """Get the current user using centralized authentication."""
    # Single-user mode - return default user info
    if user_id == DEFAULT_USER_ID:
        return UserResponse(id=str(DEFAULT_USER_ID), email="demo@talimio.com", username="Demo User")

    # Multi-user mode - get user details from Supabase
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Get token for additional user details
    auth_header = request.headers.get("Authorization", "")
    token = None

    if auth_header.startswith("Bearer "):
        token = auth_header.replace("Bearer ", "")
    else:
        cookie_token = request.cookies.get("access_token")
        if cookie_token:
            token = cookie_token.replace("Bearer ", "") if cookie_token.startswith("Bearer ") else cookie_token

    if not token:
        # We have user_id from centralized auth, but need token for details
        # This shouldn't happen if auth is working correctly
        logger.warning(f"Have user_id {user_id} but no token for details")
        raise HTTPException(status_code=401, detail="Token required for user details")

    try:
        # Get full user details (centralized auth already validated the token)
        user = await run_in_threadpool(supabase.auth.get_user, token)
        if user and user.user:
            return UserResponse(
                id=str(user.user.id),
                email=user.user.email,
                username=user.user.user_metadata.get("username", user.user.email.split("@")[0]),
            )
        # This shouldn't happen if centralized auth is working
        logger.error(f"Centralized auth passed but can't get user details for {user_id}")
        raise HTTPException(status_code=500, detail="Failed to get user details")
    except Exception as e:
        logger.exception(f"Failed to get user details for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user details") from e


@router.post("/refresh")
@auth_rate_limit  # Use stricter rate limit (5/min) to prevent refresh token abuse
async def refresh_token(request: Request, response: Response) -> RefreshResponse:
    """Refresh the access token using the refresh_token cookie."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(status_code=400, detail="Token refresh is only available with Supabase authentication")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Get refresh token from cookie
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        # Clear any stale access token
        clear_auth_cookie(response)
        raise HTTPException(status_code=401, detail="No refresh token provided")

    # Create a secure lock key using SHA256 hash (prevents collisions and protects token privacy)
    lock_key = hashlib.sha256(refresh_token_value.encode()).hexdigest()[:16]

    # Get or create a lock for this refresh attempt
    if lock_key not in refresh_locks:
        refresh_locks[lock_key] = asyncio.Lock()

    lock = refresh_locks[lock_key]

    # Try to acquire the lock with a timeout
    try:
        async with asyncio.timeout(2):  # 2 second timeout
            async with lock:
                # Use the refresh token to get a new session (run in thread pool)
                auth_response = await run_in_threadpool(
                    supabase.auth.refresh_session,
                    refresh_token_value
                )

                if not auth_response or not auth_response.session:
                    raise HTTPException(status_code=401, detail="Invalid refresh token")

                # Update both access and refresh tokens in cookies
                set_auth_cookie(response, auth_response.session.access_token)

                # Also update the refresh token cookie with the new one
                is_production = settings.ENVIRONMENT == "production"
                response.set_cookie(
                    key="refresh_token",
                    value=auth_response.session.refresh_token,
                    httponly=True,
                    secure=is_production,
                    samesite="lax" if is_production else None,
                    max_age=7 * 24 * 60 * 60,  # 7 days
                    path="/",
                )

                # Clean up locks occasionally
                await cleanup_refresh_locks()

                return RefreshResponse(
                    message="Token refreshed successfully",
                    user=UserResponse(
                        id=str(auth_response.user.id),
                        email=auth_response.user.email,
                        username=auth_response.user.user_metadata.get("username"),
                    ),
                )

    except TimeoutError as timeout_err:
        # Another request is already refreshing this token
        logger.info("Refresh already in progress for this token")
        raise HTTPException(
            status_code=409,  # Conflict
            detail="Token refresh already in progress. Please wait.",
            headers={"Retry-After": "1"}  # Client should retry after 1 second
        ) from timeout_err

    except Exception as e:
        # Check if it's a "refresh token already used" error
        error_message = str(e)
        if "Already Used" in error_message:
            # This is expected when multiple refresh attempts happen
            logger.debug("Refresh token already used - client should re-authenticate")
            # Clear the stale refresh token cookie
            response.delete_cookie("refresh_token")
            raise HTTPException(
                status_code=401,
                detail="Session expired. Please login again.",
                headers={"X-Auth-Error": "token-already-used"}
            ) from e

        # For other errors, log and return generic message
        logger.exception("Token refresh failed")
        response.delete_cookie("refresh_token")  # Clear invalid token
        raise HTTPException(
            status_code=401,
            detail="Authentication failed. Please login again."
        ) from e


@router.post("/reset-password")
@auth_rate_limit
async def reset_password(request: Request, data: PasswordResetRequest) -> MessageResponse:  # noqa: ARG001
    """Send password reset email via Supabase Auth."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(status_code=400, detail="Password reset is only available with Supabase authentication")

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Use Supabase's built-in password reset (run in thread pool)
        # According to the docs, it's resetPasswordForEmail in JS but Python uses snake_case
        await run_in_threadpool(supabase.auth.reset_password_email, data.email)
        # Don't reveal if email exists or not for security
        return MessageResponse(message="If the email exists, password reset instructions have been sent")
    except Exception:
        # Always return the same message for security (don't reveal if email exists)
        return MessageResponse(message="If the email exists, password reset instructions have been sent")


# REMOVED: Debug endpoint was a security risk (exposed auth info without authentication)
