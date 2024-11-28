from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database Settings
    DATABASE_URL: str = "sqlite:///./test.db"

    # OpenAI Settings
    openai_api_key: str | None = None

    class Config:
        env_file = ".env"
        extra = "allow"  # Allow extra fields from environment

def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
