"""Authentication routes for user login, signup, and session management."""

import contextlib
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, EmailStr
from supabase import Client
from supabase_auth.types import AuthResponse, User as SupabaseUser

from src.auth.config import supabase
from src.auth.context import CurrentAuth
from src.config.settings import get_settings
from src.middleware.security import auth_rate_limit, create_rate_limit_dependency


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
    dependencies=[Depends(create_rate_limit_dependency(auth_rate_limit))]
)
logger = logging.getLogger(__name__)


def _get_supabase_client() -> Client | None:
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        return None
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    return supabase

def _require_user_email(user: SupabaseUser, fallback_email: str | None = None) -> str:
    if user.email:
        return user.email
    if fallback_email:
        return fallback_email
    raise HTTPException(status_code=401, detail="Authenticated user is missing an email address")

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

def clear_refresh_cookie(response: Response) -> None:
    """Clear refresh token cookie."""
    settings = get_settings()
    is_production = settings.ENVIRONMENT == "production"
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=is_production,
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
async def signup(data: SignupRequest) -> SignupResponse:
    """Create a new user account."""
    supabase_client = _get_supabase_client()
    if not supabase_client:
        raise HTTPException(status_code=400, detail="Signup is only available with Supabase authentication")

    try:
        # Create user with Supabase Auth (run in thread pool to avoid blocking)
        auth_response: AuthResponse = await run_in_threadpool(
            supabase_client.auth.sign_up,
            {
                "email": data.email,
                "password": data.password,
                "options": {"data": {"username": data.username or data.email.split("@")[0]}},
            }
        )

        if not auth_response.user:
            raise HTTPException(status_code=400, detail="Failed to create user")

        user = auth_response.user
        user_email = _require_user_email(user, data.email)
        user_payload = {
            "id": str(user.id),
            "email": user_email,
            "username": user.user_metadata.get("username"),
        }

        # If email confirmation is enabled, session will be None
        if not auth_response.session:
            # Return a special response indicating email confirmation is needed
            return SignupResponse(
                user=user_payload,
                message="Please check your email to confirm your account",
                email_confirmation_required=True,
            )

        return SignupResponse(
            user=user_payload,
            access_token=auth_response.session.access_token,
            expires_in=auth_response.session.expires_in,
            email_confirmation_required=False,
        )

    except Exception as e:
        # If it's a Supabase auth error, try to get more details
        error_detail = str(e)
        if hasattr(e, "message"):
            error_detail = e.message
        elif hasattr(e, "args") and e.args:
            error_detail = str(e.args[0])

        raise HTTPException(status_code=400, detail=error_detail) from e

@router.post("/login")
async def login(response: Response, data: LoginRequest) -> LoginResponse:
    """Login with email and password."""
    supabase_client = _get_supabase_client()
    if not supabase_client:
        raise HTTPException(status_code=400, detail="Login is only available with Supabase authentication")

    settings = get_settings()

    try:
        # Authenticate with Supabase (run in thread pool to avoid blocking)
        auth_response: AuthResponse = await run_in_threadpool(
            supabase_client.auth.sign_in_with_password,
            {"email": data.email, "password": data.password}
        )

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = auth_response.user
        user_email = _require_user_email(user, data.email)

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
                id=str(user.id),
                email=user_email,
                username=user.user_metadata.get("username"),
            )
        )

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid credentials") from e

@router.post("/logout")
async def logout(_request: Request, response: Response) -> LogoutResponse:
    """Logout the current user."""
    supabase_client = _get_supabase_client()
    if not supabase_client:
        return LogoutResponse(message="Logout not required in current auth mode")

    # Clear both httpOnly cookies (this is the real logout)
    clear_auth_cookie(response)
    clear_refresh_cookie(response)

    with contextlib.suppress(Exception):
        # Try to sign out with Supabase (optional, run in thread pool)
        await run_in_threadpool(supabase_client.auth.sign_out)

    return LogoutResponse(message="Successfully logged out")

@router.get("/me")
async def get_current_user(request: Request, _auth: CurrentAuth) -> UserResponse:
    """Return the current user using Supabase (or demo user in single-user mode)."""
    settings = get_settings()
    if settings.AUTH_PROVIDER == "none":
        return UserResponse(id=str(_auth.user_id), email="demo@talimio.com", username="Demo User")

    # Supabase mode: middleware token validation already fetched the user once.
    if not hasattr(request.state, "user_email"):
        raise HTTPException(status_code=500, detail="Auth middleware did not set user_email")

    user_email: str | None = request.state.user_email
    if not user_email:
        raise HTTPException(status_code=401, detail="Authenticated user is missing an email address")

    user_username: str | None = getattr(request.state, "user_username", None)
    return UserResponse(
        id=str(_auth.user_id),
        email=user_email,
        username=user_username or user_email.split("@")[0],
    )

async def _validate_refresh_prerequisites(request: Request, response: Response) -> str:
    """Validate prerequisites for token refresh and return the refresh token."""
    if not _get_supabase_client():
        raise HTTPException(status_code=400, detail="Token refresh is only available with Supabase authentication")

    # Get refresh token from cookie
    refresh_token_value = request.cookies.get("refresh_token")
    if not refresh_token_value:
        # Clear any stale access token
        clear_auth_cookie(response)
        raise HTTPException(status_code=401, detail="No refresh token provided")

    return refresh_token_value

async def _perform_token_refresh(refresh_token_value: str, response: Response) -> RefreshResponse:
    """Perform the actual token refresh with Supabase."""
    settings = get_settings()

    supabase_client = _get_supabase_client()
    if not supabase_client:
        raise HTTPException(status_code=503, detail="Authentication service not configured")

    # Use the refresh token to get a new session (run in thread pool)
    auth_response: AuthResponse = await run_in_threadpool(
        supabase_client.auth.refresh_session,
        refresh_token_value
    )

    if not auth_response or not auth_response.session:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    user = auth_response.user if auth_response.user else auth_response.session.user
    user_email = _require_user_email(user)

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

    return RefreshResponse(
        message="Token refreshed successfully",
        user=UserResponse(
            id=str(user.id),
            email=user_email,
            username=user.user_metadata.get("username"),
        ),
    )

def _handle_refresh_error(error: Exception, response: Response) -> None:
    """Handle specific refresh token errors."""
    error_message = str(error)

    # Clear the invalid refresh token cookie in all error cases
    clear_refresh_cookie(response)

    # Handle specific refresh token errors
    if "Already Used" in error_message:
        # This is expected when multiple refresh attempts happen
        logger.debug("Refresh token already used - client should re-authenticate")
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again.",
            headers={"X-Auth-Error": "token-already-used"}
        ) from error
    if "Refresh Token Not Found" in error_message or "Invalid Refresh Token" in error_message:
        # Token doesn't exist or has expired
        logger.debug("Refresh token not found or invalid - client should re-authenticate")
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again.",
            headers={"X-Auth-Error": "token-not-found"}
        ) from error
    if "expired" in error_message.lower():
        # Token has expired
        logger.debug("Refresh token expired - client should re-authenticate")
        raise HTTPException(
            status_code=401,
            detail="Session expired. Please login again.",
            headers={"X-Auth-Error": "token-expired"}
        ) from error
    # For other unexpected errors, log with full traceback
    logger.exception("Unexpected error during token refresh")
    raise HTTPException(
        status_code=401,
        detail="Authentication failed. Please login again.",
        headers={"X-Auth-Error": "refresh-failed"}
    ) from error

@router.post("/refresh")
async def refresh_token(request: Request, response: Response) -> RefreshResponse:
    """Refresh the access token using the refresh_token cookie."""
    refresh_token_value = await _validate_refresh_prerequisites(request, response)

    try:
        return await _perform_token_refresh(refresh_token_value, response)
    except Exception as e:
        _handle_refresh_error(e, response)
        raise

@router.post("/reset-password")
async def reset_password(data: PasswordResetRequest) -> MessageResponse:
    """Send password reset email via Supabase Auth."""
    supabase_client = _get_supabase_client()
    if not supabase_client:
        raise HTTPException(status_code=400, detail="Password reset is only available with Supabase authentication")

    try:
        # Use Supabase's built-in password reset (run in thread pool)
        # According to the docs, it's resetPasswordForEmail in JS but Python uses snake_case
        await run_in_threadpool(supabase_client.auth.reset_password_email, data.email)
        # Don't reveal if email exists or not for security
        return MessageResponse(message="If the email exists, password reset instructions have been sent")
    except Exception:
        # Always return the same message for security (don't reveal if email exists)
        return MessageResponse(message="If the email exists, password reset instructions have been sent")
