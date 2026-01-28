from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.settings import get_settings


settings = get_settings()


def create_app_engine() -> AsyncEngine:
    """Create the async engine with minimal, reliable defaults."""
    database_url = settings.DATABASE_URL

    return create_async_engine(
        database_url,
        echo=False,  # Set True for SQL debugging
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )


# Create the engine
engine: AsyncEngine = create_app_engine()
