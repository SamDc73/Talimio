"""Database-backed user CRUD for local auth."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import delete, func, select

from src.auth.models import AuthSession, PasswordResetTokenUse
from src.auth.security import get_password_hash, verify_password
from src.user.models import User


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


DUMMY_HASH = get_password_hash(secrets.token_urlsafe(32))


def normalize_email(email: str) -> str:
    """Normalize email for consistent storage and lookups."""
    return email.strip().lower()


async def create_user(
    session: AsyncSession,
    *,
    email: str,
    password: str | None,
    username: str,
    full_name: str | None = None,
    is_active: bool = True,
    is_verified: bool = False,
) -> User:
    """Create a new local user."""
    normalized_email = normalize_email(email)
    hashed_password = get_password_hash(secrets.token_urlsafe(32)) if password is None else get_password_hash(password)
    user = User(
        email=normalized_email,
        username=username,
        password_hash=hashed_password,
        full_name=full_name,
        is_active=is_active,
        is_verified=is_verified,
    )
    session.add(user)
    await session.flush()
    return user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Return a user by email or None."""
    normalized_email = normalize_email(email)
    result = await session.execute(select(User).where(func.lower(User.email) == normalized_email))
    return result.scalar_one_or_none()


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User | None:
    """Return user if email/password are valid, else None (timing-safe)."""
    user = await get_user_by_email(session, email)
    if not user:
        verify_password(password, DUMMY_HASH)
        return None

    verified, updated_hash = verify_password(password, user.password_hash)
    if not verified:
        return None

    if updated_hash:
        user.password_hash = updated_hash
        session.add(user)
        await session.flush()

    return user


async def has_password_reset_jti(session: AsyncSession, *, jti: str) -> bool:
    """Return whether a password-reset token JTI has already been used."""
    result = await session.execute(select(PasswordResetTokenUse.jti).where(PasswordResetTokenUse.jti == jti))
    return result.scalar_one_or_none() is not None


async def mark_password_reset_jti_used(
    session: AsyncSession,
    *,
    jti: str,
    user_id: UUID,
    email: str,
    expires_at: datetime,
) -> None:
    """Persist a used password-reset JTI so the token cannot be replayed."""
    session.add(
        PasswordResetTokenUse(
            jti=jti,
            user_id=user_id,
            email=normalize_email(email),
            expires_at=expires_at,
        )
    )
    await session.flush()


async def increment_auth_token_version(session: AsyncSession, user: User) -> int:
    """Increment user token version and return the new value."""
    user.auth_token_version += 1
    session.add(user)
    await session.flush()
    return user.auth_token_version


def _utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(tz=UTC)


async def cleanup_auth_operational_tables(
    session: AsyncSession,
    *,
    now: datetime | None = None,
) -> dict[str, int]:
    """Delete stale rows from auth operational tables."""
    current_time = now or _utc_now()

    deleted_auth_sessions_result = await session.execute(
        delete(AuthSession).where(
            (AuthSession.expires_at < current_time)
            | ((AuthSession.revoked_at.is_not(None)) & (AuthSession.revoked_at < current_time))
        )
    )
    deleted_password_reset_result = await session.execute(
        delete(PasswordResetTokenUse).where(PasswordResetTokenUse.expires_at < current_time)
    )

    return {
        "deleted_auth_sessions": int(getattr(deleted_auth_sessions_result, "rowcount", 0) or 0),
        "deleted_password_reset_token_uses": int(getattr(deleted_password_reset_result, "rowcount", 0) or 0),
    }


async def create_auth_session(
    session: AsyncSession,
    *,
    user_id: UUID,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> AuthSession:
    """Create and persist a local auth session."""
    auth_session = AuthSession(
        user_id=user_id,
        expires_at=expires_at,
        user_agent=user_agent,
        ip_address=ip_address,
    )
    session.add(auth_session)
    await session.flush()
    return auth_session


async def get_auth_session(
    session: AsyncSession,
    *,
    session_id: UUID,
    user_id: UUID,
) -> AuthSession | None:
    """Return a local auth session by ID and owner."""
    auth_session = await session.get(AuthSession, session_id)
    if not auth_session or auth_session.user_id != user_id:
        return None
    return auth_session


async def list_auth_sessions(
    session: AsyncSession,
    *,
    user_id: UUID,
) -> list[AuthSession]:
    """List auth sessions for a user, newest first."""
    result = await session.execute(
        select(AuthSession).where(AuthSession.user_id == user_id).order_by(AuthSession.created_at.desc())
    )
    return list(result.scalars().all())


def is_auth_session_active(auth_session: AuthSession, *, now: datetime | None = None) -> bool:
    """Return whether a local auth session is active."""
    current_time = now or datetime.now(UTC)
    if auth_session.revoked_at is not None:
        return False
    return auth_session.expires_at > current_time


async def touch_auth_session(
    session: AsyncSession,
    auth_session: AuthSession,
    *,
    now: datetime | None = None,
    min_update_interval: timedelta = timedelta(minutes=1),
) -> None:
    """Update last-seen timestamp with a small write throttle."""
    current_time = now or datetime.now(UTC)
    last_seen_at = auth_session.last_seen_at
    if last_seen_at is not None and current_time - last_seen_at < min_update_interval:
        return
    auth_session.last_seen_at = current_time
    session.add(auth_session)
    await session.flush()


async def renew_auth_session(
    session: AsyncSession,
    auth_session: AuthSession,
    *,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
    now: datetime | None = None,
) -> None:
    """Renew session expiry and mark it recently seen."""
    current_time = now or datetime.now(UTC)
    auth_session.expires_at = expires_at
    auth_session.last_seen_at = current_time
    auth_session.user_agent = user_agent
    auth_session.ip_address = ip_address
    session.add(auth_session)
    await session.flush()


async def revoke_auth_session(
    session: AsyncSession,
    auth_session: AuthSession,
    *,
    revoked_at: datetime | None = None,
) -> bool:
    """Revoke a session once; returns True when updated."""
    if auth_session.revoked_at is not None:
        return False
    auth_session.revoked_at = revoked_at or datetime.now(UTC)
    session.add(auth_session)
    await session.flush()
    return True


async def revoke_all_auth_sessions(
    session: AsyncSession,
    *,
    user_id: UUID,
    revoked_at: datetime | None = None,
) -> int:
    """Revoke all active local auth sessions for a user."""
    current_time = revoked_at or datetime.now(UTC)
    auth_sessions = await list_auth_sessions(session, user_id=user_id)
    revoked_count = 0
    for auth_session in auth_sessions:
        if auth_session.revoked_at is None:
            auth_session.revoked_at = current_time
            session.add(auth_session)
            revoked_count += 1
    if revoked_count > 0:
        await session.flush()
    return revoked_count
