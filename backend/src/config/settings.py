from functools import lru_cache

from pydantic_settings import BaseSettings as PydanticBaseSettings, SettingsConfigDict


class Settings(PydanticBaseSettings):  # type: ignore[misc]
    """Application settings."""

    # API Settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database Settings
    DATABASE_URL: str

    # OpenAI Settings
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=("../.env", "../.env.local"),
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
