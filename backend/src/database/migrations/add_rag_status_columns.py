"""Add RAG status columns to books and videos tables."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_rag_status_columns_to_books(engine: AsyncEngine) -> None:
    """Add rag_status and rag_processed_at columns to books table if they don't exist."""
    async with engine.begin() as conn:
        # Check if rag_status column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'books'
                AND column_name = 'rag_status'
            """),
        )

        if not result.fetchone():
            logger.info("Adding RAG status columns to books table...")
            await conn.execute(
                text("""
                    ALTER TABLE books
                    ADD COLUMN rag_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                """),
            )
            await conn.execute(
                text("""
                    ALTER TABLE books
                    ADD COLUMN rag_processed_at TIMESTAMPTZ
                """),
            )
            logger.info("Successfully added RAG status columns to books table")
        else:
            logger.info("RAG status columns already exist in books table")


async def add_rag_status_columns_to_videos(engine: AsyncEngine) -> None:
    """Add rag_status and rag_processed_at columns to videos table if they don't exist."""
    async with engine.begin() as conn:
        # Check if rag_status column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'videos'
                AND column_name = 'rag_status'
            """),
        )

        if not result.fetchone():
            logger.info("Adding RAG status columns to videos table...")
            await conn.execute(
                text("""
                    ALTER TABLE videos
                    ADD COLUMN rag_status VARCHAR(20) NOT NULL DEFAULT 'pending'
                """),
            )
            await conn.execute(
                text("""
                    ALTER TABLE videos
                    ADD COLUMN rag_processed_at TIMESTAMPTZ
                """),
            )
            logger.info("Successfully added RAG status columns to videos table")
        else:
            logger.info("RAG status columns already exist in videos table")


async def run_rag_status_migrations(engine: AsyncEngine) -> None:
    """Run all RAG status related migrations."""
    try:
        await add_rag_status_columns_to_books(engine)
        await add_rag_status_columns_to_videos(engine)
        logger.info("All RAG status migrations completed successfully")
    except Exception as e:
        logger.exception(f"RAG status migration failed: {e}")
        raise
