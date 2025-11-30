from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings - only define what needs validation."""

    # Critical configs that need validation/type conversion
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/talimio"
    DEBUG: bool = False
    API_PORT: int = 8080
    ENVIRONMENT: str = "development"  # "development", "production"
    PLATFORM_MODE: str = "oss"  # "oss" or "cloud"
    SECRET_KEY: str = "your-secret-key-change-in-production"  # For session middleware  # noqa: S105
    MCP_TOKEN_ENCRYPTION_KEY: str | None = None

    # Database config kept minimal for Supabase session pooler

    # Auth settings
    AUTH_DISABLED: bool = False
    AUTH_PROVIDER: str = "none"  # "none" (single-user mode) or "supabase" (multi-user mode)

    # Supabase Auth (2025 API patterns)
    SUPABASE_URL: str = ""
    SUPABASE_PUBLISHABLE_KEY: str = ""  # Safe for client-side
    SUPABASE_SECRET_KEY: str = ""  # Backend only

    # Storage settings
    STORAGE_PROVIDER: str = "local"  # "r2" or "local"
    LOCAL_STORAGE_PATH: str = "uploads"  # Path for local file storage (e.g., "uploads", "/app/uploads")

    # R2 Configuration (optional)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "talimio-books"
    R2_REGION: str = "auto"

    # RAG Video Processing Configuration
    RAG_VIDEO_MAX_TOKENS: int = 512
    RAG_VIDEO_OVERLAP_TOKENS: int = 50
    RAG_VIDEO_TARGET_DURATION: int = 180  # 3 minutes in seconds
    RAG_VIDEO_SHORT_DURATION_THRESHOLD: int = 600  # 10 minutes
    RAG_VIDEO_MEDIUM_DURATION_THRESHOLD: int = 1800  # 30 minutes
    RAG_VIDEO_LONG_DURATION_CHUNK: int = 300  # 5 minutes in seconds for long videos

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

    # Feature flags for gradual rollout
    USE_MODULE_FACADES: bool = True  # Enable new facade pattern

    # AI Configuration
    @property
    def primary_llm_model(self) -> str:
        """Get primary LLM model from environment - required configuration."""
        import os

        model = os.getenv("PRIMARY_LLM_MODEL")
        if not model:
            msg = "PRIMARY_LLM_MODEL environment variable is required"
            raise ValueError(msg)
        return model

    @property
    def ai_request_timeout(self) -> int:
        """Get AI request timeout from environment."""
        import os

        # 5 minutes default for complex AI operations like lesson generation
        return int(os.getenv("AI_REQUEST_TIMEOUT", "300"))

    @property
    def ai_max_tokens_default(self) -> int:
        """Get default max tokens for AI requests."""
        import os

        return int(os.getenv("AI_MAX_TOKENS_DEFAULT", "4000"))

    @property
    def ai_temperature_default(self) -> float:
        """Get default temperature for AI requests."""
        import os

        return float(os.getenv("AI_TEMPERATURE_DEFAULT", "0.7"))

    # AI Model Configuration
    def get_model_list(self) -> list[dict]:
        """Get the model list configuration for litellm.Router."""
        primary_model = self.primary_llm_model
        return [
            {
                "model_name": "primary",
                "litellm_params": {
                    "model": primary_model,
                },
            }
        ]

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    if not settings.DATABASE_URL:
        msg = "DATABASE_URL environment variable is not set"
        raise ValueError(msg)
    return settings
