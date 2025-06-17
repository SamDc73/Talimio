"""Add archive-related columns to existing content tables."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_archive_columns_to_books(engine: AsyncEngine) -> None:
    """Add archived and archived_at columns to books table if they don't exist."""
    async with engine.begin() as conn:
        # Check if archived column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'books'
                AND column_name = 'archived'
            """),
        )

        if not result.fetchone():
            logger.info("Adding archived columns to books table...")
            await conn.execute(
                text("""
                    ALTER TABLE books
                    ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE
                """),
            )
            await conn.execute(
                text("""
                    ALTER TABLE books
                    ADD COLUMN archived_at TIMESTAMPTZ
                """),
            )
            logger.info("Successfully added archived columns to books table")
        else:
            logger.info("archived columns already exist in books table")


async def add_archive_columns_to_videos(engine: AsyncEngine) -> None:
    """Add archived and archived_at columns to videos table if they don't exist."""
    async with engine.begin() as conn:
        # Check if archived column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'videos'
                AND column_name = 'archived'
            """),
        )

        if not result.fetchone():
            logger.info("Adding archived columns to videos table...")
            await conn.execute(
                text("""
                    ALTER TABLE videos
                    ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE
                """),
            )
            await conn.execute(
                text("""
                    ALTER TABLE videos
                    ADD COLUMN archived_at TIMESTAMPTZ
                """),
            )
            logger.info("Successfully added archived columns to videos table")
        else:
            logger.info("archived columns already exist in videos table")


async def add_archive_columns_to_flashcard_decks(engine: AsyncEngine) -> None:
    """Add archived and archived_at columns to flashcard_decks table if they don't exist."""
    async with engine.begin() as conn:
        # Check if archived column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'flashcard_decks'
                AND column_name = 'archived'
            """),
        )

        if not result.fetchone():
            logger.info("Adding archived columns to flashcard_decks table...")
            await conn.execute(
                text("""
                    ALTER TABLE flashcard_decks
                    ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE
                """),
            )
            await conn.execute(
                text("""
                    ALTER TABLE flashcard_decks
                    ADD COLUMN archived_at TIMESTAMPTZ
                """),
            )
            logger.info("Successfully added archived columns to flashcard_decks table")
        else:
            logger.info("archived columns already exist in flashcard_decks table")


async def add_archive_columns_to_roadmaps(engine: AsyncEngine) -> None:
    """Add archived and archived_at columns to roadmaps table if they don't exist."""
    async with engine.begin() as conn:
        # Check if archived column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'roadmaps'
                AND column_name = 'archived'
            """),
        )

        if not result.fetchone():
            logger.info("Adding archived columns to roadmaps table...")
            await conn.execute(
                text("""
                    ALTER TABLE roadmaps
                    ADD COLUMN archived BOOLEAN NOT NULL DEFAULT FALSE
                """),
            )
            await conn.execute(
                text("""
                    ALTER TABLE roadmaps
                    ADD COLUMN archived_at TIMESTAMPTZ
                """),
            )
            logger.info("Successfully added archived columns to roadmaps table")
        else:
            logger.info("archived columns already exist in roadmaps table")


async def run_archive_migrations(engine: AsyncEngine) -> None:
    """Run all archive-related migrations."""
    try:
        await add_archive_columns_to_books(engine)
        await add_archive_columns_to_videos(engine)
        await add_archive_columns_to_flashcard_decks(engine)
        await add_archive_columns_to_roadmaps(engine)
        logger.info("All archive migrations completed successfully")
    except Exception as e:
        logger.exception(f"Archive migration failed: {e}")
        raise
