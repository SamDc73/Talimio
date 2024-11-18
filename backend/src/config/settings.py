from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    DEBUG: bool = False
    ENVIRONMENT: str = "development"

    # Database Settings
    DATABASE_URL: str = "sqlite:///./test.db"

    class Config:
        env_file = ".env"

def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
