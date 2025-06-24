"""Add timezone support to datetime columns in courses-related tables."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def update_roadmaps_datetime_columns(engine: AsyncEngine) -> None:
    """Update datetime columns in roadmaps table to use timezone."""
    async with engine.begin() as conn:
        logger.info("Updating datetime columns in roadmaps table to support timezone...")

        # Update created_at column
        await conn.execute(
            text("""
                ALTER TABLE roadmaps
                ALTER COLUMN created_at TYPE TIMESTAMPTZ
                USING created_at AT TIME ZONE 'UTC'
            """)
        )

        # Update updated_at column
        await conn.execute(
            text("""
                ALTER TABLE roadmaps
                ALTER COLUMN updated_at TYPE TIMESTAMPTZ
                USING updated_at AT TIME ZONE 'UTC'
            """)
        )

        # archived_at is already TIMESTAMPTZ from the archive migration
        logger.info("Successfully updated roadmaps datetime columns")


async def update_nodes_datetime_columns(engine: AsyncEngine) -> None:
    """Update datetime columns in nodes table to use timezone."""
    async with engine.begin() as conn:
        logger.info("Updating datetime columns in nodes table to support timezone...")

        # Update created_at column
        await conn.execute(
            text("""
                ALTER TABLE nodes
                ALTER COLUMN created_at TYPE TIMESTAMPTZ
                USING created_at AT TIME ZONE 'UTC'
            """)
        )

        # Update updated_at column
        await conn.execute(
            text("""
                ALTER TABLE nodes
                ALTER COLUMN updated_at TYPE TIMESTAMPTZ
                USING updated_at AT TIME ZONE 'UTC'
            """)
        )

        logger.info("Successfully updated nodes datetime columns")


async def update_lessons_datetime_columns(engine: AsyncEngine) -> None:
    """Update datetime columns in lessons table to use timezone."""
    async with engine.begin() as conn:
        # Check if lessons table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'lessons'
                )
            """)
        )

        if result.scalar():
            logger.info("Updating datetime columns in lessons table to support timezone...")

            # Update created_at column
            await conn.execute(
                text("""
                    ALTER TABLE lessons
                    ALTER COLUMN created_at TYPE TIMESTAMPTZ
                    USING created_at AT TIME ZONE 'UTC'
                """)
            )

            # Update updated_at column
            await conn.execute(
                text("""
                    ALTER TABLE lessons
                    ALTER COLUMN updated_at TYPE TIMESTAMPTZ
                    USING updated_at AT TIME ZONE 'UTC'
                """)
            )

            logger.info("Successfully updated lessons datetime columns")
        else:
            logger.info("Lessons table does not exist, skipping")


async def update_progress_datetime_columns(engine: AsyncEngine) -> None:
    """Update datetime columns in progress table to use timezone."""
    async with engine.begin() as conn:
        # Check if progress table exists
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'progress'
                )
            """)
        )

        if result.scalar():
            logger.info("Updating datetime columns in progress table to support timezone...")

            # Update created_at column
            await conn.execute(
                text("""
                    ALTER TABLE progress
                    ALTER COLUMN created_at TYPE TIMESTAMPTZ
                    USING created_at AT TIME ZONE 'UTC'
                """)
            )

            # Update updated_at column
            await conn.execute(
                text("""
                    ALTER TABLE progress
                    ALTER COLUMN updated_at TYPE TIMESTAMPTZ
                    USING updated_at AT TIME ZONE 'UTC'
                """)
            )

            logger.info("Successfully updated progress datetime columns")
        else:
            logger.info("Progress table does not exist, skipping")


async def add_timezone_to_datetime_columns(engine: AsyncEngine) -> None:
    """Run all timezone-related migrations for course tables."""
    try:
        await update_roadmaps_datetime_columns(engine)
        await update_nodes_datetime_columns(engine)
        await update_lessons_datetime_columns(engine)
        await update_progress_datetime_columns(engine)
        logger.info("All timezone migrations completed successfully")
    except Exception as e:
        logger.exception(f"Timezone migration failed: {e}")
        raise
