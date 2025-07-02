"""Initial database setup - ensures pgvector and base requirements are in place."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database(db_engine: AsyncEngine) -> None:
    """Initialize database with required extensions and base setup."""
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
            logger.error(f"Failed to enable pgvector extension: {e}")
            logger.error("Make sure pgvector is installed in your PostgreSQL instance")
            logger.error("For installation instructions, see: https://github.com/pgvector/pgvector")
            raise

        # Enable pg_trgm for text search (optional but useful)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        logger.info("pg_trgm extension enabled for text search")

        logger.info("Database initialization completed successfully")


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
