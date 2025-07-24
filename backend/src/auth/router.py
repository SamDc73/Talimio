"""Authentication routes for user login, signup, and session management."""

import contextlib
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr
from supabase import Client, create_client

from src.auth.dependencies import CurrentUser, EffectiveUserId, RequireAuthInMultiUser
from src.config.settings import get_settings
from src.middleware.security import auth_rate_limit


router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


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
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=True,  # Always use secure for deletion
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


def get_supabase_client() -> Client | None:
    """Get Supabase client if configured."""
    settings = get_settings()
    if not settings.SUPABASE_URL or not settings.SUPABASE_SECRET_KEY:
        return None
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)


@router.post("/signup")
@auth_rate_limit
async def signup(request: Request, data: SignupRequest) -> SignupResponse:  # noqa: ARG001
    """Create a new user account."""
    settings = get_settings()

    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(
            status_code=400,
            detail="Signup is only available with Supabase authentication"
        )

    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Create user with Supabase Auth
        auth_response = supabase.auth.sign_up({
            "email": data.email,
            "password": data.password,
            "options": {
                "data": {
                    "username": data.username or data.email.split("@")[0]
                }
            }
        })


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
                email_confirmation_required=True
            )

        return SignupResponse(
            user={
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": auth_response.user.user_metadata.get("username"),
            },
            access_token=auth_response.session.access_token,
            expires_in=auth_response.session.expires_in,
            email_confirmation_required=False
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
        raise HTTPException(
            status_code=400,
            detail="Login is only available with Supabase authentication"
        )

    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Authenticate with Supabase
        auth_response = supabase.auth.sign_in_with_password({
            "email": data.email,
            "password": data.password
        })

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
async def logout(request: Request, response: Response) -> dict[str, str]:  # noqa: ARG001
    """Logout the current user."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        return {"message": "Logout not required in current auth mode"}

    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    # Clear both httpOnly cookies (this is the real logout)
    clear_auth_cookie(response)
    response.delete_cookie(
        key="refresh_token",
        httponly=True,
        secure=True,
        samesite="lax",
    )

    with contextlib.suppress(Exception):
        # Try to sign out with Supabase (optional)
        supabase.auth.sign_out()

    return {"message": "Successfully logged out"}


@router.get("/me")
async def get_current_user(context: RequireAuthInMultiUser) -> UserResponse:
    """Get the current user (authenticated in multi-user mode, default in single-user mode)."""
    return UserResponse(
        id=str(context.user_id),
        email=context.email or "user@talmio.local",
        username=context.name or "Default User"
    )


@router.post("/refresh")
async def refresh_token(request: Request, response: Response) -> dict:
    """Refresh the access token using the refresh_token cookie."""
    settings = get_settings()
    if settings.AUTH_PROVIDER != "supabase":
        raise HTTPException(
            status_code=400,
            detail="Token refresh is only available with Supabase authentication"
        )

    supabase = get_supabase_client()
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    try:
        # Get refresh token from cookie
        refresh_token = request.cookies.get("refresh_token")
        if not refresh_token:
            raise HTTPException(status_code=401, detail="No refresh token provided")

        # Refresh the session using the refresh token
        auth_response = supabase.auth.refresh_session(refresh_token)

        if not auth_response.user or not auth_response.session:
            raise HTTPException(status_code=401, detail="Invalid refresh token")

        # Update both access and refresh tokens in cookies
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
            "message": "Token refreshed successfully",
            "user": {
                "id": str(auth_response.user.id),
                "email": auth_response.user.email,
                "username": auth_response.user.user_metadata.get("username"),
            }
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from e


# Debug endpoint to verify authentication
@router.get("/debug")
async def debug_auth(
    request: Request,
    effective_user_id: EffectiveUserId,
    current_user: CurrentUser,
) -> dict:
    """Debug endpoint to check authentication status."""
    settings = get_settings()
    auth_header = request.headers.get("Authorization")

    return {
        "auth_provider": settings.AUTH_PROVIDER,
        "has_auth_header": bool(auth_header),
        "auth_header_preview": auth_header[:50] + "..." if auth_header and len(auth_header) > 50 else auth_header,
        "effective_user_id": str(effective_user_id),  # Keep as string for JSON serialization
        "current_user": {
            "id": current_user.id if current_user else None,
            "email": current_user.email if current_user else None,
            "name": current_user.name if current_user else None,
        } if current_user else None,
        "is_default_user": effective_user_id == UUID("00000000-0000-0000-0000-000000000001"),
    }
