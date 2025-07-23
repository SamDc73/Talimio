"""UUID User Handling Unification Migration.

This migration unifies user handling across the codebase:
1. Changes user_id columns from String to UUID
2. Creates video_progress table for user-specific video progress
3. Removes non-user-specific progress columns from videos table
4. Adds performance indexes

IMPORTANT: Run this migration when there are no active users as it will
clear existing progress data to ensure data consistency.
"""

import logging

from sqlalchemy import text

from src.database.engine import engine


logger = logging.getLogger(__name__)


async def main() -> None:
    """Execute the UUID user unification migration."""
    async with engine.begin() as conn:
        logger.info("Starting UUID user unification migration...")

        # Step 1: Fix user_id types in existing tables
        try:
            await conn.execute(text("""
                -- Fix book_progress user_id type
                ALTER TABLE book_progress ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
            """))
            logger.info("✓ Updated book_progress.user_id to UUID")
        except Exception as e:
            logger.info(f"- book_progress.user_id update skipped: {e}")

        try:
            await conn.execute(text("""
                -- Fix flashcard_decks user_id type
                ALTER TABLE flashcard_decks ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
            """))
            logger.info("✓ Updated flashcard_decks.user_id to UUID")
        except Exception as e:
            logger.info(f"- flashcard_decks.user_id update skipped: {e}")

        try:
            await conn.execute(text("""
                -- Fix flashcard_reviews user_id type
                ALTER TABLE flashcard_reviews ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
            """))
            logger.info("✓ Updated flashcard_reviews.user_id to UUID")
        except Exception as e:
            logger.info(f"- flashcard_reviews.user_id update skipped: {e}")

        # Step 2: Fix AI memory system table (if it exists)
        try:
            await conn.execute(text("""
                -- Fix user_custom_instructions user_id type
                ALTER TABLE user_custom_instructions ALTER COLUMN user_id TYPE UUID USING user_id::uuid;
            """))
            logger.info("✓ Updated user_custom_instructions.user_id to UUID")
        except Exception as e:
            logger.info(f"- user_custom_instructions.user_id update skipped: {e}")

        # Step 3: Create video_progress table
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS video_progress (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                video_uuid UUID NOT NULL REFERENCES videos(uuid) ON DELETE CASCADE,
                user_id UUID NOT NULL,
                last_position FLOAT DEFAULT 0.0,
                completion_percentage FLOAT DEFAULT 0.0,
                last_watched_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(user_id, video_uuid)  -- Prevent duplicate progress per user/video
            );
        """))
        logger.info("✓ Created video_progress table")

        # Step 4: Remove progress columns from videos table
        try:
            await conn.execute(text("ALTER TABLE videos DROP COLUMN IF EXISTS last_position;"))
            logger.info("✓ Removed last_position from videos table")
        except Exception as e:
            logger.info(f"- last_position column removal skipped: {e}")

        try:
            await conn.execute(text("ALTER TABLE videos DROP COLUMN IF EXISTS completion_percentage;"))
            logger.info("✓ Removed completion_percentage from videos table")
        except Exception as e:
            logger.info(f"- completion_percentage column removal skipped: {e}")

        # Step 5: Add performance indexes
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_video_progress_user_id ON video_progress(user_id);
        """))
        logger.info("✓ Added index on video_progress.user_id")

        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_video_progress_video_uuid ON video_progress(video_uuid);
        """))
        logger.info("✓ Added index on video_progress.video_uuid")

        try:
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_custom_instructions_user_id ON user_custom_instructions(user_id);
            """))
            logger.info("✓ Added index on user_custom_instructions.user_id")
        except Exception as e:
            logger.info(f"- user_custom_instructions index creation skipped: {e}")

        logger.info("🎉 UUID user unification migration completed successfully!")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
