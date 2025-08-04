from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings - only define what needs validation."""

    # Critical configs that need validation/type conversion
    DATABASE_URL: str  # Required, validated
    DEBUG: bool = False
    API_PORT: int = 8080
    ENVIRONMENT: str = "development"  # "development", "production"
    SECRET_KEY: str = "your-secret-key-change-in-production"  # For session middleware  # noqa: S105

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

    # Feature flags for gradual rollout
    USE_MODULE_FACADES: bool = True  # Enable new facade pattern

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
