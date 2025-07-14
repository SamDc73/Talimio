from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings - only define what needs validation."""

    # Critical configs that need validation/type conversion
    DATABASE_URL: str  # Required, validated
    DEBUG: bool = False
    API_PORT: int = 8080

    # Auth settings (need type conversion)
    JWT_EXPIRE_HOURS: int = 24
    AUTH_DISABLED: bool = False

    # Storage settings
    STORAGE_PROVIDER: str = "local"  # "r2" or "local"
    LOCAL_STORAGE_PATH: str = "backend/uploads"

    # R2 Configuration (optional)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "talimio-books"
    R2_REGION: str = "auto"

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
