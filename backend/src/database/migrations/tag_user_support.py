"""Add user_id support to tags table for multi-user functionality."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def add_user_id_to_tags(engine: AsyncEngine) -> None:
    """Add user_id column to tags table and update unique constraint."""
    async with engine.begin() as conn:
        # Check if user_id column exists
        result = await conn.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'tags'
                AND column_name = 'user_id'
            """),
        )

        if not result.fetchone():
            logger.info("Adding user_id column to tags table...")

            # Add user_id column with default value for existing records
            await conn.execute(
                text("""
                    ALTER TABLE tags
                    ADD COLUMN user_id VARCHAR(100) NOT NULL DEFAULT 'default_user'
                """),
            )

            # Create index on user_id
            await conn.execute(
                text("""
                    CREATE INDEX IF NOT EXISTS idx_tags_user_id ON tags(user_id)
                """),
            )

            logger.info("Successfully added user_id column and index")
        else:
            logger.info("user_id column already exists in tags table")

        # Check if old unique constraint exists and drop it
        constraint_result = await conn.execute(
            text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'tags'
                AND constraint_type = 'UNIQUE'
                AND constraint_name = 'tags_name_key'
            """),
        )

        if constraint_result.fetchone():
            logger.info("Dropping old unique constraint on tags.name...")
            await conn.execute(
                text("ALTER TABLE tags DROP CONSTRAINT tags_name_key"),
            )
            logger.info("Successfully dropped old unique constraint")

        # Check if new unique constraint exists
        new_constraint_result = await conn.execute(
            text("""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = 'tags'
                AND constraint_type = 'UNIQUE'
                AND constraint_name = 'uq_tag_name_user'
            """),
        )

        if not new_constraint_result.fetchone():
            logger.info("Adding new unique constraint on (name, user_id)...")
            await conn.execute(
                text("""
                    ALTER TABLE tags
                    ADD CONSTRAINT uq_tag_name_user UNIQUE (name, user_id)
                """),
            )
            logger.info("Successfully added new unique constraint")
        else:
            logger.info("New unique constraint already exists")


async def run_tag_user_migrations(engine: AsyncEngine) -> None:
    """Run all tag user support migrations."""
    try:
        await add_user_id_to_tags(engine)
        logger.info("All tag user support migrations completed successfully")
    except Exception as e:
        logger.exception(f"Tag user support migration failed: {e}")
        raise
