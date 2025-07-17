"""Add toc_progress field to book_progress table."""

import asyncio
import logging

import asyncpg

from src.config import env


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def migrate() -> None:
    """Add toc_progress column to book_progress table to store chapter completion status."""
    database_url = env("DATABASE_URL")

    # Convert SQLAlchemy URL to asyncpg format
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(database_url)

    try:
        # Add toc_progress column to book_progress table
        # This stores a JSON object mapping section IDs to completion status
        await conn.execute("""
            ALTER TABLE book_progress 
            ADD COLUMN IF NOT EXISTS toc_progress JSONB DEFAULT '{}'::jsonb
        """)

        logger.info("Successfully added toc_progress column to book_progress table")

    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(migrate())
