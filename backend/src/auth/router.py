"""Authentication routes for user login, signup, and session management."""

import logging
import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, cast
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestFormStrict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from starlette.responses import RedirectResponse

from src.auth import crud as local_crud
from src.auth.context import CurrentAuth, validate_local_auth_state
from src.auth.csrf import set_csrf_cookie
from src.auth.dependencies import (
    CookieTokenOptional,
    decode_local_token_claims_optional,
    get_local_session_id_from_state,
    get_local_token_version_from_state,
    get_user_id,
)
from src.auth.emails import (
    generate_email_verification_token,
    generate_password_reset_token,
    send_reset_email,
    send_verification_email,
    verify_email_verification_token,
    verify_password_reset_token,
)
from src.auth.models import AuthSession, OAuthAccount
from src.auth.oauth import (
    consume_google_oauth_state,
    exchange_google_code_for_identity,
    get_google_client,
    store_google_oauth_state,
)
from src.auth.password_policy import (
    PasswordPolicyError,
    validate_password_policy,
)
from src.auth.schemas import (
    AuthOptionsResponse,
    ChangePasswordRequest,
    LoginResponse,
    LogoutResponse,
    MessageResponse,
    NewPasswordRequest,
    PasswordResetRequest,
    RefreshResponse,
    ResendVerificationRequest,
    ResendVerificationResponse,
    SignupRequest,
    SignupResponse,
    UserResponse,
    VerifyEmailRequest,
)
from src.auth.security import create_access_token, get_jwt_signing_key, get_password_hash, verify_password
from src.config.settings import get_settings
from src.database.session import DbSession
from src.middleware.security import get_client_ip
from src.user.models import User


router = APIRouter(
    prefix="/api/v1/auth",
    tags=["auth"],
)
logger = logging.getLogger(__name__)

_GENERIC_SIGNUP_MESSAGE = "Signup request received. If eligible, you can sign in with your credentials."

_VERIFICATION_RESEND_COOLDOWN_SECONDS = 60
_VERIFICATION_RESEND_MAX_ATTEMPTS = 3
_VERIFICATION_RESEND_WINDOW = timedelta(minutes=30)
_VERIFICATION_RESEND_LIMIT_MESSAGE = (
    "Too many verification email requests. Please contact support if you still haven't received the email."
)
_GENERIC_RESEND_VERIFICATION_MESSAGE = "If the account exists, a verification email has been sent"


async def _require_local_provider() -> None:
    """Block endpoints that are only valid in local-auth mode."""
    if get_settings().AUTH_PROVIDER != "local":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This endpoint is only available with local authentication",
        )


def set_auth_cookie(response: Response, token: str) -> None:
    """Set httpOnly auth cookie (secure!)."""
    settings = get_settings()
    is_production = settings.ENVIRONMENT == "production"
    secure_cookie = settings.AUTH_COOKIE_SECURE or is_production
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=settings.AUTH_COOKIE_HTTPONLY,  # Can't be accessed by JS (XSS protection)
        secure=secure_cookie,
        # In development, don't set SameSite to avoid proxy/localhost friction.
        samesite=settings.AUTH_COOKIE_SAMESITE if is_production else None,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",  # Ensure cookie is available for all paths
    )


def clear_auth_cookie(response: Response) -> None:
    """Clear auth cookie on logout."""
    settings = get_settings()
    is_production = settings.ENVIRONMENT == "production"
    secure_cookie = settings.AUTH_COOKIE_SECURE or is_production
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        httponly=settings.AUTH_COOKIE_HTTPONLY,
        secure=secure_cookie,
        samesite=settings.AUTH_COOKIE_SAMESITE if is_production else None,
        path="/",
    )


def _get_request_user_agent(request: Request) -> str | None:
    """Return truncated user-agent for auth session visibility."""
    user_agent = request.headers.get("user-agent")
    if not user_agent:
        return None
    return user_agent[:512]


async def _issue_local_auth_cookie(
    request: Request,
    response: Response,
    session: DbSession,
    user: User,
    *,
    existing_session_id: UUID | None = None,
) -> UUID:
    """Create or renew a local auth session and set the cookie JWT."""
    settings = get_settings()
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    expires_at = datetime.now(UTC) + expires_delta
    user_agent = _get_request_user_agent(request)
    ip_address = get_client_ip(request)[:64]

    auth_session: AuthSession | None = None
    if existing_session_id is not None:
        current_session = await local_crud.get_auth_session(session, session_id=existing_session_id, user_id=user.id)
        if current_session and local_crud.is_auth_session_active(current_session):
            await local_crud.renew_auth_session(
                session,
                current_session,
                expires_at=expires_at,
                user_agent=user_agent,
                ip_address=ip_address,
            )
            auth_session = current_session

    if auth_session is None:
        auth_session = await local_crud.create_auth_session(
            session,
            user_id=user.id,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )

    jwt_token = create_access_token(
        user.id,
        expires_delta,
        token_version=user.auth_token_version,
        session_id=auth_session.id,
    )
    set_auth_cookie(response, jwt_token)
    return auth_session.id


_USERNAME_MIN_LENGTH = 5
_USERNAME_MAX_LENGTH = 24
_USERNAME_ALLOWED_PATTERN = re.compile(r"^[a-z0-9._]+$")
_USERNAME_START_END_PATTERN = re.compile(r"^[a-z0-9].*[a-z0-9]$")
_USERNAME_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9._]+")
_AUTO_USERNAME_FALLBACK_BASE = "learner"
_AUTO_USERNAME_SUFFIX_DIGITS = 4
_AUTO_USERNAME_MAX_ATTEMPTS = 30
_AUTO_USERNAME_BASE_MAX_LENGTH = _USERNAME_MAX_LENGTH - _AUTO_USERNAME_SUFFIX_DIGITS - 1


def _validate_password_or_raise(password: str) -> None:
    try:
        validate_password_policy(password)
    except PasswordPolicyError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error


def _normalize_username(raw_value: str) -> str:
    """Normalize a username for storage and comparisons."""
    return raw_value.strip().lower()


def _validate_username_or_raise(username: str) -> None:
    """Validate username format rules for account creation."""
    if len(username) < _USERNAME_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username must be at least {_USERNAME_MIN_LENGTH} characters",
        )
    if len(username) > _USERNAME_MAX_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username must be at most {_USERNAME_MAX_LENGTH} characters",
        )
    if not _USERNAME_ALLOWED_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username can only contain letters, numbers, underscores, and periods",
        )
    if not _USERNAME_START_END_PATTERN.fullmatch(username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must start and end with a letter or number",
        )
    if ".." in username or "__" in username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot contain repeated separators",
        )


def _derive_auto_username_base(source: str) -> str:
    """Create a safe username base from a human-readable source value."""
    normalized_base = _normalize_username(source)
    normalized_base = _USERNAME_NORMALIZE_PATTERN.sub("_", normalized_base)
    normalized_base = re.sub(r"[._]{2,}", "_", normalized_base)
    normalized_base = normalized_base.strip("._")

    if not normalized_base:
        normalized_base = _AUTO_USERNAME_FALLBACK_BASE

    normalized_base = normalized_base[:_AUTO_USERNAME_BASE_MAX_LENGTH].rstrip("._")
    if not normalized_base:
        normalized_base = _AUTO_USERNAME_FALLBACK_BASE

    if not normalized_base[0].isalnum():
        normalized_base = f"{_AUTO_USERNAME_FALLBACK_BASE}_{normalized_base}"
        normalized_base = normalized_base[:_AUTO_USERNAME_BASE_MAX_LENGTH].rstrip("._")

    if not normalized_base or not normalized_base[0].isalnum() or not normalized_base[-1].isalnum():
        normalized_base = _AUTO_USERNAME_FALLBACK_BASE

    return normalized_base


async def _username_exists(session: DbSession, username: str) -> bool:
    """Return whether a normalized username already exists (case-insensitive)."""
    existing_username = await session.execute(select(User.id).where(func.lower(User.username) == username))
    return existing_username.scalar_one_or_none() is not None


async def _ensure_unique_custom_username(session: DbSession, desired: str) -> str:
    """Validate and reserve a custom username provided by the user."""
    normalized_username = _normalize_username(desired)
    _validate_username_or_raise(normalized_username)

    if await _username_exists(session, normalized_username):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is unavailable, please try another")

    return normalized_username


async def _generate_unique_auto_username(session: DbSession, *, source: str) -> str:
    """Generate an available username that always includes numeric suffixes."""
    username_base = _derive_auto_username_base(source)

    for _ in range(_AUTO_USERNAME_MAX_ATTEMPTS):
        random_suffix = f"{secrets.randbelow(10 ** _AUTO_USERNAME_SUFFIX_DIGITS):0{_AUTO_USERNAME_SUFFIX_DIGITS}d}"
        candidate = f"{username_base}_{random_suffix}"
        _validate_username_or_raise(candidate)

        if not await _username_exists(session, candidate):
            return candidate

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unable to auto-generate a username right now. Please provide one manually.",
    )


async def _resolve_signup_username(session: DbSession, *, full_name: str, username: str | None) -> str:
    """Resolve signup username from either custom input or backend auto-generation."""
    if username and username.strip():
        return await _ensure_unique_custom_username(session, username)
    return await _generate_unique_auto_username(session, source=full_name)


@router.get("/options")
async def get_auth_options(response: Response) -> AuthOptionsResponse:
    """Return frontend-safe auth options."""
    settings = get_settings()
    google_client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value()
    google_oauth_available = settings.AUTH_PROVIDER == "local" and bool(
        settings.GOOGLE_OAUTH_CLIENT_ID and google_client_secret
    )
    set_csrf_cookie(response)
    response.headers["Cache-Control"] = "no-store"
    return AuthOptionsResponse(provider=settings.AUTH_PROVIDER, google_oauth_available=google_oauth_available)


@router.post("/signup")
async def signup(request: Request, response: Response, session: DbSession, data: SignupRequest) -> SignupResponse:
    """Create a new user account."""
    settings = get_settings()
    normalized_email = local_crud.normalize_email(str(data.email))

    if settings.AUTH_PROVIDER == "local":
        existing = await local_crud.get_user_by_email(session, normalized_email)
        if existing:
            return SignupResponse(
                message=_GENERIC_SIGNUP_MESSAGE,
                email_confirmation_required=True,
            )

        _validate_password_or_raise(data.password)

        username = await _resolve_signup_username(session, full_name=data.full_name, username=data.username)
        try:
            user = await local_crud.create_user(
                session,
                email=normalized_email,
                password=data.password,
                username=username,
                full_name=data.full_name,
                is_verified=not settings.AUTH_REQUIRE_EMAIL_VERIFICATION,
            )
            if settings.AUTH_REQUIRE_EMAIL_VERIFICATION:
                verification_token = generate_email_verification_token(normalized_email)
                try:
                    await send_verification_email(email=normalized_email, token=verification_token)
                except (httpx.HTTPError, ValueError) as error:
                    await session.rollback()
                    logger.warning(
                        "Signup verification email failed; user creation rolled back",
                        extra={"email": normalized_email, "auth_provider": settings.AUTH_PROVIDER},
                        exc_info=True,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Unable to send verification email right now. Please try again.",
                    ) from error

            await session.commit()
        except IntegrityError:
            await session.rollback()
            return SignupResponse(
                message=_GENERIC_SIGNUP_MESSAGE,
                email_confirmation_required=True,
            )

        if settings.AUTH_REQUIRE_EMAIL_VERIFICATION:
            return SignupResponse(
                message="Please check your email to verify your account.",
                email_confirmation_required=True,
            )

        await _issue_local_auth_cookie(request, response, session, user)

        return SignupResponse(user=UserResponse.from_model(user), email_confirmation_required=False)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Signup is only available with local authentication",
    )


@router.post(
    "/resend-verification",
    dependencies=[
        Depends(_require_local_provider),
    ],
)
async def resend_verification(session: DbSession, data: ResendVerificationRequest) -> ResendVerificationResponse:
    """Resend account verification instructions when local email verification is enabled."""
    settings = get_settings()
    normalized_email = local_crud.normalize_email(str(data.email))
    user = await local_crud.get_user_by_email(session, normalized_email)

    if not (user and user.is_active and not user.is_verified and settings.AUTH_REQUIRE_EMAIL_VERIFICATION):
        return ResendVerificationResponse(
            message=_GENERIC_RESEND_VERIFICATION_MESSAGE,
            cooldown_seconds=_VERIFICATION_RESEND_COOLDOWN_SECONDS,
        )

    now = datetime.now(UTC)
    window_started_at = user.verification_email_resend_window_started_at
    if window_started_at is None or now - window_started_at >= _VERIFICATION_RESEND_WINDOW:
        user.verification_email_resend_window_started_at = now
        user.verification_email_resend_attempts = 0

    if user.verification_email_resend_attempts >= _VERIFICATION_RESEND_MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=_VERIFICATION_RESEND_LIMIT_MESSAGE,
        )

    last_sent_at = user.verification_email_last_sent_at
    if last_sent_at is not None:
        elapsed_seconds = int((now - last_sent_at).total_seconds())
        if elapsed_seconds < _VERIFICATION_RESEND_COOLDOWN_SECONDS:
            retry_after_seconds = max(_VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed_seconds, 1)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Please wait {retry_after_seconds} seconds before requesting another verification email.",
                headers={"Retry-After": str(retry_after_seconds)},
            )

    verification_token = generate_email_verification_token(normalized_email)
    try:
        await send_verification_email(email=normalized_email, token=verification_token)
    except (httpx.HTTPError, ValueError):
        logger.warning(
            "Failed to resend verification email",
            extra={"email": normalized_email, "auth_provider": settings.AUTH_PROVIDER},
            exc_info=True,
        )

    user.verification_email_last_sent_at = now
    user.verification_email_resend_attempts += 1
    session.add(user)
    await session.commit()

    return ResendVerificationResponse(
        message=_GENERIC_RESEND_VERIFICATION_MESSAGE,
        cooldown_seconds=_VERIFICATION_RESEND_COOLDOWN_SECONDS,
    )


@router.post("/login")
async def login(
    request: Request,
    response: Response,
    session: DbSession,
    form_data: Annotated[OAuth2PasswordRequestFormStrict, Depends()],
) -> LoginResponse:
    """Login with email and password."""
    settings = get_settings()
    normalized_email = local_crud.normalize_email(form_data.username)

    if settings.AUTH_PROVIDER == "local":
        user = await local_crud.authenticate(session, email=normalized_email, password=form_data.password)
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

        if settings.AUTH_REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your email before signing in"
            )

        await _issue_local_auth_cookie(request, response, session, user)
        return LoginResponse(user=UserResponse.from_model(user))

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Login is only available with local authentication",
    )


@router.post("/logout")
async def logout(
    response: Response,
    session: DbSession,
    auth_token: CookieTokenOptional,
) -> LogoutResponse:
    """Logout the current user."""
    settings = get_settings()

    if settings.AUTH_PROVIDER == "local":
        claims = decode_local_token_claims_optional(auth_token, jwt_secret=get_jwt_signing_key())
        if claims:
            try:
                _user, auth_session = await validate_local_auth_state(
                    session,
                    user_id=claims.user_id,
                    token_version=claims.token_version,
                    token_session_id=claims.session_id,
                    touch_session=False,
                )
            except HTTPException:
                auth_session = None

            if auth_session is not None:
                await local_crud.revoke_auth_session(session, auth_session)
        clear_auth_cookie(response)
        return LogoutResponse(message="Successfully logged out")

    clear_auth_cookie(response)
    return LogoutResponse(message="Successfully logged out")


@router.get("/me")
async def get_current_user(_request: Request, _auth: CurrentAuth) -> UserResponse:
    """Return the current user (or demo user in single-user mode)."""
    settings = get_settings()
    if settings.AUTH_PROVIDER == "none":
        return UserResponse(id=str(_auth.user_id), email="demo@talimio.com", username="Demo User")

    if settings.AUTH_PROVIDER == "local":
        user = _auth.local_user
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Authentication context unavailable",
            )
        return UserResponse.from_model(user)

    logger.error("Unknown auth provider configured for /auth/me: %s", settings.AUTH_PROVIDER)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication provider is not supported",
    )


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    session: DbSession,
    auth_token: CookieTokenOptional,
) -> RefreshResponse:
    """Refresh the access token (local mode only)."""
    settings = get_settings()

    if settings.AUTH_PROVIDER == "local":
        if not auth_token:
            clear_auth_cookie(response)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        try:
            user_id = await get_user_id(request, token=auth_token)
            token_version = get_local_token_version_from_state(request)
            token_session_id = get_local_session_id_from_state(request)
            user, _auth_session = await validate_local_auth_state(
                session,
                user_id=user_id,
                token_version=token_version,
                token_session_id=token_session_id,
                touch_session=False,
            )
        except HTTPException:
            clear_auth_cookie(response)
            raise

        await _issue_local_auth_cookie(
            request,
            response,
            session,
            user,
            existing_session_id=token_session_id,
        )
        return RefreshResponse(message="Token refreshed successfully", user=UserResponse.from_model(user))

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Token refresh is not available in current auth mode",
    )


@router.post(
    "/forgot-password",
    dependencies=[Depends(_require_local_provider)],
)
async def forgot_password(session: DbSession, data: PasswordResetRequest) -> MessageResponse:
    """Send password reset instructions (local mode only)."""
    normalized_email = local_crud.normalize_email(str(data.email))

    user = await local_crud.get_user_by_email(session, normalized_email)
    if user and user.is_active:
        token = generate_password_reset_token(normalized_email)
        try:
            await send_reset_email(email=normalized_email, token=token)
        except (httpx.HTTPError, ValueError):
            logger.warning(
                "Failed to send password reset email",
                extra={"email": normalized_email, "auth_provider": get_settings().AUTH_PROVIDER},
                exc_info=True,
            )

    return MessageResponse(message="If the email exists, password reset instructions have been sent")


@router.post(
    "/reset-password",
    dependencies=[Depends(_require_local_provider)],
)
async def reset_password(session: DbSession, data: NewPasswordRequest) -> MessageResponse:
    """Apply a local password reset token."""
    reset_claims = verify_password_reset_token(data.token)
    if not reset_claims:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    if await local_crud.has_password_reset_jti(session, jti=reset_claims.jti):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    normalized_email = local_crud.normalize_email(reset_claims.email)
    user = await local_crud.get_user_by_email(session, normalized_email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    _validate_password_or_raise(data.new_password)
    user.password_hash = get_password_hash(data.new_password)
    session.add(user)
    await local_crud.increment_auth_token_version(session, user)
    await local_crud.revoke_all_auth_sessions(session, user_id=user.id)

    try:
        await local_crud.mark_password_reset_jti_used(
            session,
            jti=reset_claims.jti,
            user_id=user.id,
            email=normalized_email,
            expires_at=reset_claims.expires_at,
        )
        await session.commit()
    except IntegrityError as error:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token") from error

    return MessageResponse(message="Password updated")


@router.post(
    "/verify",
    dependencies=[Depends(_require_local_provider)],
)
async def verify_email(session: DbSession, data: VerifyEmailRequest) -> MessageResponse:
    """Apply a local email verification token."""
    verification_claims = verify_email_verification_token(data.token)
    if not verification_claims:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    normalized_email = local_crud.normalize_email(verification_claims.email)
    user = await local_crud.get_user_by_email(session, normalized_email)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token")

    if user.is_verified:
        return MessageResponse(message="Email already verified")

    user.is_verified = True
    session.add(user)
    await session.commit()
    return MessageResponse(message="Email verified")


@router.post(
    "/change-password",
    dependencies=[Depends(_require_local_provider)],
)
async def change_password(
    response: Response,
    auth: CurrentAuth,
    data: ChangePasswordRequest,
) -> MessageResponse:
    """Change password for the currently authenticated local account."""
    user = auth.local_user
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    verified, _ = verify_password(data.current_password, user.password_hash)
    if not verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")

    _validate_password_or_raise(data.new_password)
    user.password_hash = get_password_hash(data.new_password)
    auth.session.add(user)
    await local_crud.increment_auth_token_version(auth.session, user)
    await local_crud.revoke_all_auth_sessions(auth.session, user_id=user.id)
    await auth.session.commit()
    clear_auth_cookie(response)
    return MessageResponse(message="Password updated. Please sign in again.")


@router.delete(
    "/account",
    dependencies=[Depends(_require_local_provider)],
)
async def deactivate_account(response: Response, auth: CurrentAuth) -> MessageResponse:
    """Deactivate the authenticated account and revoke all sessions."""
    user = auth.local_user
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user.is_active = False
    auth.session.add(user)
    await local_crud.increment_auth_token_version(auth.session, user)
    await local_crud.revoke_all_auth_sessions(auth.session, user_id=user.id)
    await auth.session.commit()
    clear_auth_cookie(response)
    return MessageResponse(message="Account deactivated")


@router.get(
    "/google/authorize",
    response_model=None,
    dependencies=[Depends(_require_local_provider)],
)
async def google_authorize(request: Request) -> RedirectResponse:
    """Start Google OAuth (local mode only)."""
    client = get_google_client()
    if not client:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Google OAuth is not configured")

    oauth_state = secrets.token_urlsafe(32)
    oauth_nonce = secrets.token_urlsafe(32)
    store_google_oauth_state(request, state=oauth_state, nonce=oauth_nonce)

    redirect_uri = str(request.url_for("google_callback"))
    authorization_url = await client.get_authorization_url(
        redirect_uri=redirect_uri,
        state=oauth_state,
        scope=["openid", "email", "profile"],
        extras_params=cast("Any", {"nonce": oauth_nonce}),
    )
    return RedirectResponse(authorization_url)


@router.get(
    "/google/callback",
    name="google_callback",
    response_model=None,
    dependencies=[Depends(_require_local_provider)],
)
async def google_callback(
    request: Request,
    session: DbSession,
    code: str,
    state: str | None = None,
) -> Response:
    """Handle Google OAuth callback, set auth cookie, and redirect to frontend."""
    settings = get_settings()
    client = get_google_client()
    if not client:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Google OAuth is not configured")

    expected_state, expected_nonce = consume_google_oauth_state(request)
    if not state or not secrets.compare_digest(state, expected_state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    redirect_uri = str(request.url_for("google_callback"))
    identity = await exchange_google_code_for_identity(
        client,
        code=code,
        redirect_uri=redirect_uri,
        expected_nonce=expected_nonce,
    )
    normalized_email = local_crud.normalize_email(identity.email)

    oauth = await session.execute(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == identity.provider_user_id,
        )
    )
    oauth_account = oauth.scalar_one_or_none()

    user: User | None = None
    if oauth_account:
        user = await session.get(User, oauth_account.user_id)

    if not user:
        user = await local_crud.get_user_by_email(session, normalized_email)

    if not user:
        username = await _generate_unique_auto_username(session, source=normalized_email.split("@")[0])
        user = await local_crud.create_user(
            session,
            email=normalized_email,
            password=None,
            username=username,
            is_verified=True,
        )

    if not oauth_account:
        oauth_account = OAuthAccount(
            user_id=user.id,
            provider="google",
            provider_user_id=identity.provider_user_id,
        )
        session.add(oauth_account)

    redirect_response = RedirectResponse(settings.FRONTEND_URL)
    await _issue_local_auth_cookie(request, redirect_response, session, user)
    await session.commit()
    return redirect_response
