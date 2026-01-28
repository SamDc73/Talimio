from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings - only define what needs validation."""

    # Critical configs that need validation/type conversion
    DATABASE_URL: str = "postgresql+psycopg://postgres:postgres@localhost:5432/talimio"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"  # "development", "production"
    PLATFORM_MODE: str = "oss"  # "oss" or "cloud"
    SECRET_KEY: str = "your-secret-key-change-in-production"  # For session middleware  # noqa: S105
    MCP_TOKEN_ENCRYPTION_KEY: str | None = None

    # Server Configuration (used when running src/main.py directly)
    API_HOST: str = "127.0.0.1"
    API_PORT: int = 8080

    # Auth settings
    AUTH_PROVIDER: str = "none"  # "none" (single-user mode) or "supabase" (multi-user mode)

    # Supabase Auth (2025 API patterns)
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""  # Safe for client-side

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

    # Security / rate-limits
    DISABLE_RATE_LIMITS: bool = False

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
