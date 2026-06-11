"""Pydantic schemas for auth API requests and responses."""


from pydantic import EmailStr, Field, field_validator

from src.config.schema_casing import CamelModel
from src.config.settings import get_settings
from src.user.models import User


_MIN_PASSWORD_LENGTH = get_settings().AUTH_PASSWORD_MIN_LENGTH
_MAX_PASSWORD_LENGTH = 128


class SignupRequest(CamelModel):
    """Signup request model."""

    full_name: str = Field(min_length=1, max_length=160)
    email: EmailStr
    password: str = Field(min_length=_MIN_PASSWORD_LENGTH, max_length=_MAX_PASSWORD_LENGTH)
    username: str | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        """Require a non-empty full name after trimming whitespace."""
        normalized_full_name = value.strip()
        if not normalized_full_name:
            msg = "Full name is required"
            raise ValueError(msg)
        return normalized_full_name


class SignupResponse(CamelModel):
    """Signup response model - can handle both immediate auth and email confirmation."""

    user: UserResponse | None = None
    message: str | None = None
    email_confirmation_required: bool = False


class UserResponse(CamelModel):
    """User response model."""

    id: str
    email: str
    full_name: str | None = None
    username: str | None = None

    @classmethod
    def from_model(cls, user: User) -> UserResponse:
        """Build a response payload from a persisted user."""
        return cls(
            id=str(user.id),
            email=user.email,
            full_name=user.full_name,
            username=user.username,
        )


class LoginResponse(CamelModel):
    """Login response model."""

    user: UserResponse


class LogoutResponse(CamelModel):
    """Logout response model."""

    message: str


class MessageResponse(CamelModel):
    """Generic message response."""

    message: str


class PasswordResetRequest(CamelModel):
    """Password reset request model."""

    email: EmailStr


class NewPasswordRequest(CamelModel):
    """Apply password reset using a reset token."""

    token: str
    new_password: str = Field(min_length=_MIN_PASSWORD_LENGTH, max_length=_MAX_PASSWORD_LENGTH)


class ChangePasswordRequest(CamelModel):
    """Apply an authenticated password change."""

    current_password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)
    new_password: str = Field(min_length=_MIN_PASSWORD_LENGTH, max_length=_MAX_PASSWORD_LENGTH)


class ResendVerificationRequest(CamelModel):
    """Request model for email verification resend."""

    email: EmailStr


class ResendVerificationResponse(CamelModel):
    """Response model for email verification resend."""

    message: str
    cooldown_seconds: int | None = None


class VerifyEmailRequest(CamelModel):
    """Apply email verification token."""

    token: str


class PasswordPolicyResponse(CamelModel):
    """Password policy configuration exposed for frontend validation parity."""

    min_length: int
    require_uppercase: bool
    require_lowercase: bool
    require_digit: bool
    require_symbol: bool
    disallow_whitespace: bool


class AuthOptionsResponse(CamelModel):
    """Public auth configuration for the frontend."""

    provider: str
    google_oauth_available: bool
    password_policy: PasswordPolicyResponse
