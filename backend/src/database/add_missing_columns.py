"""Add missing columns to existing tables using SQLAlchemy."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_table_of_contents_column(engine: AsyncEngine) -> None:
    """Add table_of_contents column to books table if it doesn't exist."""
    async with engine.begin() as conn:
        # Check if column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'books'
                AND column_name = 'table_of_contents'
            """),
        )

        if not result.fetchone():
            logger.info("Adding table_of_contents column to books table...")
            await conn.execute(
                text("""
                    ALTER TABLE books
                    ADD COLUMN table_of_contents TEXT
                """),
            )
            logger.info("Successfully added table_of_contents column")
        else:
            logger.info("table_of_contents column already exists")


async def run_migrations(engine: AsyncEngine) -> None:
    """Run all pending migrations."""
    try:
        await add_table_of_contents_column(engine)
        logger.info("All migrations completed successfully")
    except Exception as e:
        logger.exception(f"Migration failed: {e}")
        raise
