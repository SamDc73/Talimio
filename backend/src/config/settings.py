import os
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database Settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")  # Provide a default empty string

    # OpenAI Settings
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),  # Try multiple env files
        env_file_encoding="utf-8",
        extra="allow",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    settings = Settings()
    if not settings.DATABASE_URL:
        msg = "DATABASE_URL environment variable is not set"
        raise ValueError(msg)
    return settings
