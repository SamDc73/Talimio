#!/usr/bin/env python3
"""
Migration: Create highlights table for text highlighting feature

This migration:
1. Creates highlights table with user_id, content_type, content_id, and highlight_data
2. Adds proper indexes for efficient queries
3. Includes foreign key constraints for data integrity
"""

import asyncio
import logging

from sqlalchemy import text

from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


async def upgrade():
    """Create highlights table for storing text highlights."""
    async with async_session_maker() as session:
        try:
            # Create highlights table
            await session.execute(
                text("""
                CREATE TABLE IF NOT EXISTS highlights (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL,
                    content_type VARCHAR(50) NOT NULL,
                    content_id UUID NOT NULL,
                    highlight_data JSONB NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    
                    CONSTRAINT valid_content_type CHECK (
                        content_type IN ('book', 'course', 'video')
                    )
                );
            """)
            )
            logger.info("✅ Created highlights table")

            # Create composite index for user and content queries
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_highlights_user_content 
                ON highlights (user_id, content_type, content_id);
            """)
            )
            logger.info("✅ Created user_content composite index")

            # Create GIN index for JSONB queries
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_highlights_data_gin 
                ON highlights USING GIN (highlight_data);
            """)
            )
            logger.info("✅ Created GIN index for highlight_data")

            # Create index on created_at for sorting
            await session.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_highlights_created_at 
                ON highlights (created_at DESC);
            """)
            )
            logger.info("✅ Created created_at index for efficient sorting")

            await session.commit()
            logger.info("🎉 Migration completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise


async def downgrade():
    """Remove highlights table and indexes."""
    async with async_session_maker() as session:
        try:
            # Drop the highlights table (CASCADE will drop indexes too)
            await session.execute(text("DROP TABLE IF EXISTS highlights CASCADE;"))

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

    print("🚀 Running highlights table migration...")
    asyncio.run(upgrade())
    print("✅ Migration complete!")
