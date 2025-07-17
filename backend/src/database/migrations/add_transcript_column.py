"""Add transcript column to videos table."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_transcript_to_videos(engine: AsyncEngine) -> None:
    """Add transcript column to videos table if it doesn't exist."""
    async with engine.begin() as conn:
        # Check if transcript column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'videos'
                AND column_name = 'transcript'
            """),
        )

        if not result.fetchone():
            logger.info("Adding transcript column to videos table...")
            await conn.execute(
                text("""
                    ALTER TABLE videos
                    ADD COLUMN transcript TEXT
                """),
            )
            logger.info("Successfully added transcript column to videos table")
        else:
            logger.info("transcript column already exists in videos table")


async def add_transcript_column() -> None:
    """Main migration function."""
    from src.database.engine import engine
    try:
        await add_transcript_to_videos(engine)
        logger.info("Transcript migration completed successfully")
    except Exception as e:
        logger.exception(f"Transcript migration failed: {e}")
        raise


# Alias for auto_migrate.py compatibility
main = add_transcript_column
