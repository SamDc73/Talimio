"""Pydantic schemas for auth API requests and responses."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from src.config.settings import get_settings


if TYPE_CHECKING:
    from src.user.models import User


_MIN_PASSWORD_LENGTH = get_settings().AUTH_PASSWORD_MIN_LENGTH
_MAX_PASSWORD_LENGTH = 128


def _to_camel(string: str) -> str:
    """Convert snake_case names to camelCase for API payloads."""
    parts = string.split("_")
    return parts[0] + "".join(part.capitalize() for part in parts[1:])


_AUTH_SCHEMA_CONFIG = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class SignupRequest(BaseModel):
    """Signup request model."""

    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=_MIN_PASSWORD_LENGTH, max_length=_MAX_PASSWORD_LENGTH)
    username: str | None = None

    model_config = _AUTH_SCHEMA_CONFIG

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Require a non-empty full name after trimming whitespace."""
        normalized_full_name = value.strip()
        if not normalized_full_name:
            msg = "Full name is required"
            raise ValueError(msg)
        return normalized_full_name


class SignupResponse(BaseModel):
    """Signup response model - can handle both immediate auth and email confirmation."""

    user: UserResponse | None = None
    message: str | None = None
    email_confirmation_required: bool = False

    model_config = _AUTH_SCHEMA_CONFIG


class UserResponse(BaseModel):
    """User response model."""

    id: str
    email: str
    full_name: str | None = None
    username: str | None = None

    model_config = _AUTH_SCHEMA_CONFIG

    @classmethod
    def from_model(cls, user: User) -> UserResponse:
        """Build a response payload from a persisted user."""
        return cls(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            username=user.username,
        )


class LoginResponse(BaseModel):
    """Login response model."""

    user: UserResponse

    model_config = _AUTH_SCHEMA_CONFIG


class LogoutResponse(BaseModel):
    """Logout response model."""

    message: str

    model_config = _AUTH_SCHEMA_CONFIG


class RefreshResponse(BaseModel):
    """Token refresh response model."""

    message: str
    user: UserResponse

    model_config = _AUTH_SCHEMA_CONFIG


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str

    model_config = _AUTH_SCHEMA_CONFIG


class PasswordResetRequest(BaseModel):
    """Password reset request model."""

    email: EmailStr

    model_config = _AUTH_SCHEMA_CONFIG


class NewPasswordRequest(BaseModel):
    """Apply password reset using a reset token."""

    token: str
    new_password: str = Field(min_length=_MIN_PASSWORD_LENGTH, max_length=_MAX_PASSWORD_LENGTH)

    model_config = _AUTH_SCHEMA_CONFIG


class ChangePasswordRequest(BaseModel):
    """Apply an authenticated password change."""

    current_password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=_MIN_PASSWORD_LENGTH, max_length=_MAX_PASSWORD_LENGTH)

    model_config = _AUTH_SCHEMA_CONFIG


class ResendVerificationRequest(BaseModel):
    """Request model for email verification resend."""

    email: EmailStr

    model_config = _AUTH_SCHEMA_CONFIG


class VerifyEmailRequest(BaseModel):
    """Apply email verification token."""

    token: str

    model_config = _AUTH_SCHEMA_CONFIG


class AuthOptionsResponse(BaseModel):
    """Public auth configuration for the frontend."""

    provider: str
    google_oauth_available: bool

    model_config = _AUTH_SCHEMA_CONFIG
