from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_SETTINGS_ENV_FILES = (
    _BACKEND_ROOT / ".env",
    _BACKEND_ROOT / ".env.local",
)


class Settings(BaseSettings):
    """Application settings - only define what needs validation."""

    # Critical configs that need validation/type conversion
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/talimio"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # "development", "production"
    PLATFORM_MODE: Literal["cloud", "oss"] = "cloud"
    AUTH_SECRET_KEY: SecretStr = SecretStr("")  # Required for JWT/session/CSRF signing
    MCP_TOKEN_ENCRYPTION_KEY: SecretStr | None = None

    # Server Configuration (used when running src/main.py directly)
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8080

    # Auth settings
    AUTH_PROVIDER: str = "none"  # "none" (single-user) | "local" (email/password in DB)

    # Local (template-style) Auth
    AUTH_REQUIRE_EMAIL_VERIFICATION: bool = False
    TRUSTED_PROXY_CIDRS: str = ""

    # Password policy defaults aligned with frontend behavior (min length + zxcvbn feedback).
    AUTH_PASSWORD_MIN_LENGTH: int = 8
    AUTH_PASSWORD_REQUIRE_UPPERCASE: bool = False
    AUTH_PASSWORD_REQUIRE_LOWERCASE: bool = False
    AUTH_PASSWORD_REQUIRE_DIGIT: bool = False
    AUTH_PASSWORD_REQUIRE_SYMBOL: bool = False
    AUTH_PASSWORD_DISALLOW_WHITESPACE: bool = False

    # Cookie config
    AUTH_COOKIE_NAME: str = "access_token"
    AUTH_COOKIE_SECURE: bool = False  # True in production
    AUTH_COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    AUTH_COOKIE_HTTPONLY: bool = True

    # Frontend URL (used for auth redirects / emails)
    FRONTEND_URL: str = "http://localhost:5173"
    # App URL for auth user-facing flows (email links, OAuth callback redirect).
    # Defaults to FRONTEND_URL when unset.
    FRONTEND_APP_URL: str = ""

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
    CODE_EXECUTION_LLM_MODEL: str | None = None
    AI_REQUEST_TIMEOUT: int = 300

    # AI Tooling Configuration
    AI_ENABLED_TOOLS: str = ""  # Comma-separated allowlist; empty means allow all.
    AI_DISABLED_TOOLS: str = ""  # Comma-separated blocklist.
    AI_ENABLE_EXPERIMENTAL_MCP_TOOLS: bool = False
    AI_ENABLE_HOSTED_WEB_SEARCH: bool = True
    EXA_API_KEY: SecretStr | None = None
    EXA_SEARCH_TIMEOUT_SECONDS: float = 12.0
    EXA_SEARCH_MAX_RESULTS: int = 5

    # Assistant UI Configuration
    AVAILABLE_MODELS: str = ""  # Comma-separated additional models for UI pickers.

    # Domain-specific model overrides
    TAGGING_LLM_MODEL: str | None = None
    GRADING_COACH_LLM_MODEL: str | None = None

    # Code Execution (E2B)
    E2B_SANDBOX_TTL: int = 600
    E2B_MAX_ACTIVE_SCOPES: int = 8
    CODE_EXECUTION_MAX_COMPLETION_TOKENS: int = 4096
    E2B_SDK_LOG_LEVEL: str = "WARNING"
    E2B_TEMPLATE_COURSE: str = ""
    E2B_TEMPLATE_LAB: str = ""
    E2B_TEMPLATE_ASSISTANT: str = ""
    E2B_ALLOW_INTERNET_COURSE: bool = True
    E2B_ALLOW_INTERNET_LAB: bool = True
    E2B_ALLOW_INTERNET_ASSISTANT: bool = True

    # Release metadata
    RELEASE_VERSION: str = ""
    K_REVISION: str = ""

    # Observability
    OTEL_ENABLED: bool | None = None
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""
    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT: str = ""
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT: str = ""
    OTEL_EXPORTER_OTLP_HEADERS: str = ""
    OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS: int = 10
    OTEL_RESOURCE_ATTRIBUTES: str = ""

    # Migrations
    MIGRATIONS_AUTO_APPLY: bool = False
    MIGRATIONS_VERBOSE: bool = False
    MIGRATIONS_DIR: str | None = None
    _OSS_DEFAULT_SIGNING_SEED = "talimio-oss-local-dev-signing-seed"

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url_scheme(cls, value: str) -> str:
        """Ensure psycopg3 URL scheme is used."""
        if not value.startswith("postgresql+psycopg://"):
            msg = "DATABASE_URL must use postgresql+psycopg:// for psycopg3"
            raise ValueError(msg)
        return value

    @field_validator(
        "AUTH_PASSWORD_MIN_LENGTH",
    )
    @classmethod
    def validate_positive_integers(cls, value: int) -> int:
        """Ensure integer auth settings are positive."""
        if value <= 0:
            msg = "Auth settings integer values must be greater than zero"
            raise ValueError(msg)
        return value

    @field_validator("EXA_SEARCH_TIMEOUT_SECONDS")
    @classmethod
    def validate_exa_timeout(cls, value: float) -> float:
        """Ensure Exa search timeout is positive."""
        if value <= 0:
            msg = "EXA_SEARCH_TIMEOUT_SECONDS must be greater than zero"
            raise ValueError(msg)
        return value

    @field_validator("EXA_SEARCH_MAX_RESULTS")
    @classmethod
    def validate_exa_max_results(cls, value: int) -> int:
        """Ensure Exa max results stays in a practical range."""
        if value < 1:
            msg = "EXA_SEARCH_MAX_RESULTS must be >= 1"
            raise ValueError(msg)
        if value > 10:
            msg = "EXA_SEARCH_MAX_RESULTS must be <= 10"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def apply_platform_mode_defaults(self) -> Settings:
        """Apply mode-specific defaults when values are not explicitly configured."""
        model_fields_set = self.model_fields_set

        if self.PLATFORM_MODE == "cloud":
            if "AUTH_PROVIDER" not in model_fields_set:
                self.AUTH_PROVIDER = "local"
            return self

        # PLATFORM_MODE == "oss": local-first defaults for self-hosting.
        if "AUTH_PROVIDER" not in model_fields_set:
            self.AUTH_PROVIDER = "local"

        if "AUTH_REQUIRE_EMAIL_VERIFICATION" not in model_fields_set:
            self.AUTH_REQUIRE_EMAIL_VERIFICATION = False

        if "STORAGE_PROVIDER" not in model_fields_set:
            self.STORAGE_PROVIDER = "local"

        if "MIGRATIONS_AUTO_APPLY" not in model_fields_set:
            self.MIGRATIONS_AUTO_APPLY = True

        auth_secret_key = self.AUTH_SECRET_KEY.get_secret_value().strip()
        if not auth_secret_key and "AUTH_SECRET_KEY" not in model_fields_set:
            self.AUTH_SECRET_KEY = SecretStr(self._OSS_DEFAULT_SIGNING_SEED)

        return self

    @model_validator(mode="after")
    def validate_auth_secret_key_required(self) -> Settings:
        """Require AUTH_SECRET_KEY to be configured and non-empty."""
        auth_secret_key = self.AUTH_SECRET_KEY
        if not auth_secret_key.get_secret_value().strip():
            msg = "AUTH_SECRET_KEY environment variable is required"
            raise ValueError(msg)
        return self

    @property
    def primary_llm_model(self) -> str:
        """Get primary LLM model from environment with available-model fallback."""
        explicit_model = (self.PRIMARY_LLM_MODEL or "").strip()
        if explicit_model:
            return explicit_model

        available_raw = self.AVAILABLE_MODELS
        if available_raw:
            available_models = [candidate.strip() for candidate in available_raw.split(",") if candidate.strip()]
            if available_models:
                return available_models[0]

        msg = "PRIMARY_LLM_MODEL environment variable is required (or set AVAILABLE_MODELS with at least one model)"
        raise ValueError(msg)

    @property
    def ai_request_timeout(self) -> int:
        """Get AI request timeout from environment."""
        return self.AI_REQUEST_TIMEOUT

    @property
    def frontend_app_url(self) -> str:
        """Get the frontend app URL used for user-facing auth navigation."""
        configured = self.FRONTEND_APP_URL.strip()
        return configured or self.FRONTEND_URL

    @property
    def otel_enabled(self) -> bool:
        """Return the effective OpenTelemetry enablement."""
        configured = self.OTEL_ENABLED
        if configured is not None:
            return configured
        return self.ENVIRONMENT == "production" or bool(self.K_REVISION.strip())

    model_config = SettingsConfigDict(
        env_file=_SETTINGS_ENV_FILES,
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
