"""Database configuration with automatic fallback strategy."""

import asyncio
import logging

import asyncpg
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import create_async_engine


logger = logging.getLogger(__name__)


class DatabaseConfig(BaseSettings):
    """Database configuration with fallback support."""

    # Primary database (Supabase)
    supabase_url: str = (
        "postgresql+asyncpg://postgres:02ML8dXOrCAbSCbz@db.sznfaqmsormdwmafnrrt.supabase.co:5432/postgres"
    )

    # Fallback database (local)
    local_url: str = "postgresql+asyncpg://samdc:1234@192.168.8.188:5432/talimio"

    # Connection settings
    connection_timeout: int = 10
    max_retries: int = 3

    model_config = SettingsConfigDict(env_prefix="DB_")


async def test_database_connection(database_url: str, timeout: int = 10) -> bool:  # noqa: ASYNC109, PT028
    """Test if database connection is working."""
    try:
        # Extract connection details from URL
        if "postgresql+asyncpg://" in database_url:
            # Convert SQLAlchemy URL to asyncpg format
            asyncpg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
            asyncpg_url = asyncpg_url.split("?")[0]  # Remove query parameters
        else:
            asyncpg_url = database_url

        # Test connection
        conn = await asyncio.wait_for(asyncpg.connect(asyncpg_url), timeout=timeout)
        await conn.close()
        logger.info(f"Database connection successful: {database_url.split('@')[1].split('/')[0]}")
        return True

    except Exception as e:
        logger.warning(f"Database connection failed: {e}")
        return False


async def get_database_url() -> str:
    """Get working database URL with automatic fallback."""
    config = DatabaseConfig()

    # Try Supabase first
    logger.info("Testing Supabase database connection...")
    if await test_database_connection(config.supabase_url, config.connection_timeout):
        logger.info("Using Supabase database")
        return config.supabase_url

    # Fallback to local database
    logger.info("Supabase unavailable, testing local database...")
    if await test_database_connection(config.local_url, config.connection_timeout):
        logger.info("Using local database")
        return config.local_url

    # No database available
    msg = "No database connections available"
    raise ConnectionError(msg)


def create_database_engine(database_url: str):  # noqa: ANN201
    """Create database engine with optimal settings."""
    return create_async_engine(
        database_url,
        echo=False,
        pool_size=10,
        max_overflow=20,
        pool_timeout=30,
        pool_recycle=3600,
        # Force IPv4 and optimize connection
        connect_args={
            "server_settings": {"application_name": "talimio_backend", "jit": "off"},
            "command_timeout": 10,
        },
    )
