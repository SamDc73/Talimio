"""Authentication dependencies for FastAPI."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.schemas import TokenData
from src.auth.utils import decode_token
from src.config.settings import get_settings
from src.database.session import get_db_session


settings = get_settings()


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User:
    """Get current authenticated user from JWT token."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenData(user_id=str(user_id), username=payload.get("username"))
    except ValueError:
        raise credentials_exception from None

    # Get user from database
    result = await db.execute(select(User).where(User.id == token_data.user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )

    return user


async def get_current_user_optional(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> User | None:
    """Get current user if auth enabled, or None if disabled."""
    if settings.AUTH_DISABLED:
        return None

    if not token:
        return None

    try:
        return await get_current_user(token, db)
    except HTTPException:
        return None


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure user is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_admin_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Ensure user has admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user
