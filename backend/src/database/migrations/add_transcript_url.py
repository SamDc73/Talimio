"""Add transcript_url column to videos table."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_transcript_url_to_videos(engine: AsyncEngine) -> None:
    """Add transcript_url column to videos table if it doesn't exist."""
    async with engine.begin() as conn:
        # Check if transcript_url column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'videos'
                AND column_name = 'transcript_url'
            """),
        )

        if not result.fetchone():
            logger.info("Adding transcript_url column to videos table...")
            await conn.execute(
                text("""
                    ALTER TABLE videos
                    ADD COLUMN transcript_url VARCHAR(500)
                """),
            )
            logger.info("Successfully added transcript_url column to videos table")
        else:
            logger.info("transcript_url column already exists in videos table")


async def run_transcript_url_migration(engine: AsyncEngine) -> None:
    """Run transcript URL migration."""
    try:
        await add_transcript_url_to_videos(engine)
        logger.info("Transcript URL migration completed successfully")
    except Exception as e:
        logger.exception(f"Transcript URL migration failed: {e}")
        raise
