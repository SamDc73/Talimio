"""Add tagging-related columns to existing tables."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_tags_json_to_roadmaps(engine: AsyncEngine) -> None:
    """Add tags_json column to roadmaps table if it doesn't exist."""
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'roadmaps'
                AND column_name = 'tags_json'
            """),
        )

        if not result.fetchone():
            logger.info("Adding tags_json column to roadmaps table...")
            await conn.execute(
                text("""
                    ALTER TABLE roadmaps
                    ADD COLUMN tags_json TEXT
                """),
            )
            logger.info("Successfully added tags_json column")
        else:
            logger.info("tags_json column already exists in roadmaps table")


async def run_tagging_migrations(engine: AsyncEngine) -> None:
    """Run all tagging-related migrations."""
    try:
        await add_tags_json_to_roadmaps(engine)
        logger.info("All tagging migrations completed successfully")
    except Exception as e:
        logger.exception(f"Tagging migration failed: {e}")
        raise
