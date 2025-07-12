"""Utility functions for authentication."""

from datetime import datetime, timedelta, UTC

import jwt
from passlib.context import CryptContext

from src.config.settings import get_settings


settings = get_settings()


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plain password."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hash."""
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(user_id: str, username: str) -> str:
    """Create a JWT access token."""
    expire = datetime.now(UTC) + timedelta(hours=settings.jwt_expire_hours)
    data = {
        "sub": user_id,  # subject (user ID)
        "username": username,
        "exp": expire,
        "iat": datetime.now(UTC),  # issued at
    }
    return jwt.encode(data, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token."""
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.ExpiredSignatureError:
        msg = "Token has expired"
        raise ValueError(msg) from None
    except jwt.InvalidTokenError:
        msg = "Invalid token"
        raise ValueError(msg) from None
