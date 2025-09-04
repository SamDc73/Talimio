"""Simplified database initialization - creates extensions and tables."""

import asyncio
import logging
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

# Import all models to register them with Base metadata
from src.books.models import *  # noqa: F403
from src.courses.models import *  # noqa: F403
from src.flashcards.models import *  # noqa: F403
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

        # 3. Create default user if needed
        logger.info("Ensuring default user exists...")
        await _ensure_default_user(conn)

        logger.info("Database initialization completed successfully")


async def _ensure_default_user(conn: AsyncConnection) -> None:
    """Create default user if it doesn't exist."""
    try:
        # Check if users table exists and has any users
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
            # Check if default user exists
            result = await conn.execute(text("SELECT COUNT(*) FROM users"))
            user_count = result.scalar()

            if user_count == 0:
                # Create default user
                default_user_id = str(uuid4())
                await conn.execute(
                    text("""
                    INSERT INTO users (id, email, name, created_at, updated_at)
                    VALUES (:id, 'default@talimio.com', 'Default User', NOW(), NOW())
                """),
                    {"id": default_user_id},
                )
                logger.info(f"Created default user with ID: {default_user_id}")
            else:
                logger.info(f"Found {user_count} existing users, skipping default user creation")
        else:
            logger.info("Users table doesn't exist yet, skipping default user creation")
    except Exception as e:
        logger.warning(f"Could not create default user (this may be normal): {e}")


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
