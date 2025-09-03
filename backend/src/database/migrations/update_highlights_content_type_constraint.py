#!/usr/bin/env python3
"""
Migration: Update highlights table content_type constraint

This migration:
1. Drops the old constraint that allowed 'lesson'
2. Creates a new constraint that allows 'course' instead of 'lesson'
3. Maintains backward compatibility for existing 'book' and 'video' data

This aligns the database constraint with the rest of the codebase which uses 'course' instead of 'lesson'.
"""

import asyncio
import logging

from sqlalchemy import text

from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


async def upgrade():
    """Update the content_type constraint to use 'course' instead of 'lesson'."""
    async with async_session_maker() as session:
        try:
            # Drop the old constraint
            await session.execute(text("ALTER TABLE highlights DROP CONSTRAINT IF EXISTS valid_content_type;"))
            logger.info("✅ Dropped old content_type constraint")

            # Add the new constraint with 'course' instead of 'lesson'
            await session.execute(
                text("""
                ALTER TABLE highlights ADD CONSTRAINT valid_content_type 
                CHECK (content_type IN ('book', 'course', 'video'));
                """)
            )
            logger.info("✅ Added new content_type constraint with 'course'")

            await session.commit()
            logger.info("🎉 Migration completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise


async def downgrade():
    """Revert to the old constraint with 'lesson' instead of 'course'."""
    async with async_session_maker() as session:
        try:
            # Drop the new constraint
            await session.execute(text("ALTER TABLE highlights DROP CONSTRAINT IF EXISTS valid_content_type;"))
            logger.info("✅ Dropped new content_type constraint")

            # Add back the old constraint with 'lesson'
            await session.execute(
                text("""
                ALTER TABLE highlights ADD CONSTRAINT valid_content_type 
                CHECK (content_type IN ('book', 'lesson', 'video'));
                """)
            )
            logger.info("✅ Restored old content_type constraint with 'lesson'")

            await session.commit()
            logger.info("✅ Downgrade completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Downgrade failed: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Load environment
    from dotenv import load_dotenv

    load_dotenv()

    print("🚀 Running highlights content_type constraint update migration...")
    asyncio.run(upgrade())
    print("✅ Migration complete!")
