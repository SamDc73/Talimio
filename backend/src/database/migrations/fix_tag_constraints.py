"""Fix tag constraints - remove old unique constraint on name only."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


logger = logging.getLogger(__name__)


async def fix_tag_constraints(engine: AsyncEngine) -> None:
    """Remove old unique constraint on tags.name and ensure proper constraint exists."""
    async with engine.begin() as conn:
        # Check if old unique index exists
        old_index_result = await conn.execute(
            text("""
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = 'tags'
                AND indexname = 'ix_tags_name'
            """),
        )

        if old_index_result.fetchone():
            logger.info("Dropping old unique index ix_tags_name...")
            await conn.execute(
                text("DROP INDEX IF EXISTS ix_tags_name"),
            )
            logger.info("Successfully dropped old unique index")

        # Check if the proper constraint exists
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
            logger.info("Adding proper unique constraint on (name, user_id)...")
            await conn.execute(
                text("""
                    ALTER TABLE tags
                    ADD CONSTRAINT uq_tag_name_user UNIQUE (name, user_id)
                """),
            )
            logger.info("Successfully added proper unique constraint")
        else:
            logger.info("Proper unique constraint already exists")


async def run_tag_constraint_migration(engine: AsyncEngine) -> None:
    """Run tag constraint migration."""
    try:
        await fix_tag_constraints(engine)
        logger.info("Tag constraint migration completed successfully")
    except Exception as e:
        logger.exception(f"Tag constraint migration failed: {e}")
        raise
