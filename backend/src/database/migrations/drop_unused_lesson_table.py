"""
Migration: Drop the unused 'lesson' table.

This table is redundant - we use 'lessons' table instead.
The 'lesson' table has 0 rows and is not referenced in any active code.
"""

import logging
import sys
from pathlib import Path

# Add the backend directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from src.database.session import async_session_maker

logger = logging.getLogger(__name__)


async def upgrade() -> None:
    """Drop the unused 'lesson' table."""
    async with async_session_maker() as session:
        try:
            # Drop the unused table
            await session.execute(text("DROP TABLE IF EXISTS lesson CASCADE"))
            await session.commit()
            logger.info("✅ Dropped unused 'lesson' table")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Failed to drop 'lesson' table: {e}")
            raise


async def downgrade() -> None:
    """Recreate the 'lesson' table (for rollback purposes)."""
    async with async_session_maker() as session:
        try:
            # Recreate the table structure
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS lesson (
                    id UUID PRIMARY KEY,
                    node_id UUID REFERENCES nodes(id),
                    course_id UUID REFERENCES roadmaps(id),
                    slug TEXT UNIQUE,
                    md_source TEXT NOT NULL,
                    html_cache TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Add foreign key constraints
            await session.execute(text("""
                ALTER TABLE lesson 
                ADD CONSTRAINT fk_lesson_node_id 
                FOREIGN KEY (node_id) REFERENCES nodes(id)
            """))
            
            await session.execute(text("""
                ALTER TABLE lesson 
                ADD CONSTRAINT fk_lesson_course_id 
                FOREIGN KEY (course_id) REFERENCES roadmaps(id)
            """))
            
            await session.commit()
            logger.info("✅ Recreated 'lesson' table for rollback")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Failed to recreate 'lesson' table: {e}")
            raise


if __name__ == "__main__":
    import asyncio
    asyncio.run(upgrade())