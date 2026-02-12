from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings - only define what needs validation."""

    # Critical configs that need validation/type conversion
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/talimio"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # "development", "production"
    PLATFORM_MODE: str = "oss"  # "oss" or "cloud"
    AUTH_SECRET_KEY: SecretStr = SecretStr("")  # Required for JWT/session/CSRF signing
    MCP_TOKEN_ENCRYPTION_KEY: SecretStr | None = None

    # Server Configuration (used when running src/main.py directly)
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8080

    # Auth settings
    AUTH_PROVIDER: str = "none"  # "none" (single-user) | "local" (email/password in DB)

    # Local (template-style) Auth
    # 60 minutes is a common access-token/session lifetime when paired with refresh/rotation.
    # You can increase this in production if you want "stay logged in" behavior.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    AUTH_REQUIRE_EMAIL_VERIFICATION: bool = False
    TRUSTED_PROXY_CIDRS: str = ""

    # Password policy
    AUTH_PASSWORD_MIN_LENGTH: int = 12
    AUTH_PASSWORD_REQUIRE_UPPERCASE: bool = True
    AUTH_PASSWORD_REQUIRE_LOWERCASE: bool = True
    AUTH_PASSWORD_REQUIRE_DIGIT: bool = True
    AUTH_PASSWORD_REQUIRE_SYMBOL: bool = True
    AUTH_PASSWORD_DISALLOW_WHITESPACE: bool = True

    # Cookie config
    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: bool = False  # True in production
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_HTTPONLY: bool = True

    # Frontend URL (used for auth redirects / emails)
    FRONTEND_URL: str = "http://localhost:5173"

    # CORS (for browser-based clients)
    # Comma-separated list of allowed origins (e.g. "https://talimio.com,http://localhost:5173").
    # If empty, the app allows localhost dev origins + the origin derived from FRONTEND_URL.
    CORS_ALLOW_ORIGINS: str = ""

    # Resend API (password reset + verification emails)
    RESEND_API_KEY: SecretStr = SecretStr("")
    EMAILS_FROM_EMAIL: str = ""
    EMAILS_FROM_NAME: str = "Talimio"

    # Password reset tokens
    # 1 hour is a common password reset link lifetime.
    EMAIL_RESET_TOKEN_EXPIRE_HOURS: int = 1

    # Google OAuth
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: SecretStr = SecretStr("")

    # Storage settings
    STORAGE_PROVIDER: str = "local"  # "r2" or "local"
    LOCAL_STORAGE_PATH: str = "uploads"  # Path for local file storage (e.g., "uploads", "/app/uploads")

    # R2 Configuration (optional)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "talimio-books"
    R2_REGION: str = "auto"

    # Adaptive Learning Configuration
    ADAPTIVE_SIMILARITY_THRESHOLD: float = 0.78  # Threshold for concept similarity detection
    ADAPTIVE_UNLOCK_MASTERY_THRESHOLD: float = (
        0.5  # Mastery level to unlock prerequisites (aligned with LECTOR initial mastery band)
    )
    ADAPTIVE_CONFUSION_LAMBDA: float = 0.3  # Weight for confusion risk in scheduling
    ADAPTIVE_RISK_RECENT_K: int = 3  # Number of recent concepts to consider for sigma context

    # Learning Algorithm Parameters
    LEARNING_DELTA_CORRECT: float = 0.18  # Mastery increase for correct answers
    LEARNING_DELTA_INCORRECT: float = -0.25  # Mastery decrease for incorrect answers
    LATENCY_PENALTY_MAX: float = 0.12  # Maximum latency penalty
    LATENCY_PENALTY_MULTIPLIER: float = 10000.0  # Latency penalty calculation divisor
    REVIEW_INTERVALS_BY_RATING: dict[int, int] = {
        1: 5,  # 5 minutes for rating 1
        2: 60,  # 1 hour for rating 2
        3: 240,  # 4 hours for rating 3
        4: 360,  # 6 hours for rating 4
    }
    EXPOSURE_MULTIPLIER: float = 0.2  # Softer exposure-based interval adjustment
    DURATION_ADJUSTMENT_MIN: float = 0.6  # Minimum duration-based adjustment factor
    DURATION_ADJUSTMENT_MAX: float = 1.2  # Maximum duration-based adjustment factor
    DURATION_BASE_MS: int = 90000  # Base duration for adjustment calculations (90 seconds)

    # AI Configuration
    PRIMARY_LLM_MODEL: str | None = None
    AI_REQUEST_TIMEOUT: int = 300

    # AI Tooling Configuration
    AI_ENABLED_TOOLS: str = ""  # Comma-separated allowlist; empty means allow all.
    AI_DISABLED_TOOLS: str = ""  # Comma-separated blocklist.

    # Assistant UI Configuration
    AVAILABLE_MODELS: str = ""  # Comma-separated additional models for UI pickers.

    # Domain-specific model overrides
    TAGGING_LLM_MODEL: str | None = None
    GRADING_COACH_LLM_MODEL: str | None = None

    # Code Execution (E2B)
    E2B_SANDBOX_TTL: int = 600
    E2B_SDK_LOG_LEVEL: str = "WARNING"

    # Migrations
    MIGRATIONS_AUTO_APPLY: bool = True
    MIGRATIONS_VERBOSE: bool = False
    MIGRATIONS_DIR: str | None = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url_scheme(cls, value: str) -> str:
        """Ensure psycopg3 URL scheme is used."""
        if not value.startswith("postgresql+psycopg://"):
            msg = "DATABASE_URL must use postgresql+psycopg:// for psycopg3"
            raise ValueError(msg)
        return value

    @field_validator(
        "ACCESS_TOKEN_EXPIRE_MINUTES",
        "AUTH_PASSWORD_MIN_LENGTH",
    )
    @classmethod
    def validate_positive_integers(cls, value: int) -> int:
        """Ensure integer auth settings are positive."""
        if value <= 0:
            msg = "Auth settings integer values must be greater than zero"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_auth_secret_key_required(self) -> "Settings":
        """Require AUTH_SECRET_KEY to be configured and non-empty."""
        auth_secret_key = self.AUTH_SECRET_KEY
        if not auth_secret_key.get_secret_value().strip():
            msg = "AUTH_SECRET_KEY environment variable is required"
            raise ValueError(msg)
        return self

    @property
    def primary_llm_model(self) -> str:
        """Get primary LLM model from environment - required configuration."""
        model = self.PRIMARY_LLM_MODEL
        if not model:
            msg = "PRIMARY_LLM_MODEL environment variable is required"
            raise ValueError(msg)
        return model

    @property
    def ai_request_timeout(self) -> int:
        """Get AI request timeout from environment."""
        return self.AI_REQUEST_TIMEOUT

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
