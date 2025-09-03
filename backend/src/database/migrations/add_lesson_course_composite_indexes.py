#!/usr/bin/env python3
"""
Migration: Add composite indexes for lesson+course performance optimization.

This migration adds indexes for Phase 2 performance improvements:
1. Composite index for (lesson_id, course_id) queries
2. Composite index for (course_id, user_id) queries
3. Parent ordering index for hierarchical queries
"""

import asyncio
import logging

from sqlalchemy import text

from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


async def upgrade() -> None:
    """Add composite indexes for optimized lesson and course queries."""
    async with async_session_maker() as session:
        try:
            # Add composite index for lesson+course queries (nodes table)
            # This optimizes the JOIN in our single-query lesson loading
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_lesson_course
                ON nodes (id, roadmap_id);
            """)
            )
            logger.info("✅ Created lesson+course composite index on nodes")

            # Add composite index for course+user queries (roadmaps table)
            # This optimizes user isolation queries
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_roadmaps_course_user
                ON roadmaps (id, user_id);
            """)
            )
            logger.info("✅ Created course+user composite index on roadmaps")

            # Add parent ordering index for hierarchical queries
            # This optimizes parent-child relationship queries
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_parent_order
                ON nodes (parent_id, "order") WHERE parent_id IS NOT NULL;
            """)
            )
            logger.info("✅ Created parent+order index for hierarchical queries")

            # Add index for roadmap_id queries on nodes (if not already exists)
            # This optimizes the JOIN operation in our optimized query
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_nodes_roadmap_id
                ON nodes (roadmap_id);
            """)
            )
            logger.info("✅ Created roadmap_id index on nodes")

            # Add index for user_id queries on roadmaps (if not already exists)
            # This optimizes user isolation filtering
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id
                ON roadmaps (user_id);
            """)
            )
            logger.info("✅ Created user_id index on roadmaps")

            await session.commit()
            logger.info("🎉 Performance indexes migration completed successfully")

        except Exception as e:
            await session.rollback()
            logger.exception(f"❌ Migration failed: {e}")
            raise


async def downgrade() -> None:
    """Remove performance indexes."""
    async with async_session_maker() as session:
        try:
            # Drop all the indexes we created
            await session.execute(text("DROP INDEX IF EXISTS idx_nodes_lesson_course;"))
            await session.execute(text("DROP INDEX IF EXISTS idx_roadmaps_course_user;"))
            await session.execute(text("DROP INDEX IF EXISTS idx_nodes_parent_order;"))
            await session.execute(text("DROP INDEX IF EXISTS idx_nodes_roadmap_id;"))
            await session.execute(text("DROP INDEX IF EXISTS idx_roadmaps_user_id;"))

            await session.commit()
            logger.info("✅ Downgrade completed successfully")

        except Exception as e:
            await session.rollback()
            logger.exception(f"❌ Downgrade failed: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Load environment
    from dotenv import load_dotenv

    load_dotenv()

    logger.info("🚀 Running performance indexes migration...")
    asyncio.run(upgrade())
    logger.info("✅ Migration complete!")
