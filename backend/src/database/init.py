"""Simplified database initialization - creates extensions and tables."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.auth.config import DEFAULT_USER_ID

# Import all models to register them with Base metadata
from src.books.models import *  # noqa: F403
from src.courses.models import *  # noqa: F403
from src.tagging.models import *  # noqa: F403
from src.user.models import *  # noqa: F403
from src.videos.models import *  # noqa: F403

from .base import Base
from .engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database(db_engine: AsyncEngine) -> None:
    """Initialize database with required extensions and create all tables."""
    async with db_engine.begin() as conn:
        # Clean any stale prepared statements before metadata operations
        # This prevents "prepared statement already exists" errors during startup
        await conn.exec_driver_sql("DEALLOCATE ALL")

        # 1. Enable required extensions
        logger.info("Enabling required PostgreSQL extensions...")

        # Enable UUID generation
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        logger.info("uuid-ossp extension enabled")

        # Enable pgvector for embeddings - CRITICAL for RAG system
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")
        except Exception as e:
            logger.exception(f"Failed to enable pgvector extension: {e}")
            logger.exception("Make sure pgvector is installed in your PostgreSQL instance")
            logger.exception("For installation instructions, see: https://github.com/pgvector/pgvector")
            raise

        # Enable pg_trgm for text search (optional but useful)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        logger.info("pg_trgm extension enabled for text search")

        # 2. Create all tables from models
        logger.info("Creating database tables from models...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("All tables created successfully")

        # 3. Create default user if needed (for self-hosters with AUTH_PROVIDER=none)
        logger.info("Ensuring default user exists...")
        await _ensure_default_user(conn)

        logger.info("Database initialization completed successfully")


async def _ensure_default_user(conn: AsyncConnection) -> None:
    """Create default user for self-hosters (AUTH_PROVIDER=none)."""
    try:
        # Check if users table exists
        result = await conn.execute(
            text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'users'
            )
        """)
        )
        table_exists = result.scalar()

        if table_exists:
            # Check if default user already exists
            result = await conn.execute(
                text("SELECT COUNT(*) FROM users WHERE id = :id"),
                {"id": str(DEFAULT_USER_ID)}
            )
            user_exists = result.scalar() > 0

            if not user_exists:
                # Create default user for self-hosters
                await conn.execute(
                    text("""
                    INSERT INTO users (id, username, email, password_hash, role, is_active, created_at, updated_at)
                    VALUES (:id, 'default', 'user@localhost', 'not_used_in_single_user_mode', 'user', true, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                    {"id": str(DEFAULT_USER_ID)},
                )
                logger.info(f"Created default user for self-hosters with ID: {DEFAULT_USER_ID}")
            else:
                logger.info("Default user already exists")
        else:
            logger.info("Users table doesn't exist yet, will be created by SQLAlchemy")
    except Exception as e:
        logger.warning(f"Could not create default user (non-critical for single-user mode): {e}")


async def main() -> None:
    """Run the initialization."""
    try:
        await init_database(engine)
        logger.info("Database initialization completed!")
    except Exception:
        logger.exception("Database initialization failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
