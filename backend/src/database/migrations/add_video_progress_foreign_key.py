"""Add foreign key constraint to video_progress.user_id.

This migration adds the missing foreign key constraint from video_progress.user_id
to users.id that was overlooked in the initial UUID unification migration.
"""

import logging

from sqlalchemy import text

from src.database.engine import engine


logger = logging.getLogger(__name__)


async def main() -> None:
    """Add foreign key constraint to video_progress.user_id."""
    async with engine.begin() as conn:
        logger.info("Adding foreign key constraint to video_progress.user_id...")

        try:
            # First, let's check if there are any orphaned video_progress records
            result = await conn.execute(text("""
                SELECT COUNT(*) as orphaned_count
                FROM video_progress vp
                WHERE NOT EXISTS (
                    SELECT 1 FROM users u WHERE u.id = vp.user_id
                );
            """))
            orphaned_count = result.scalar()

            if orphaned_count > 0:
                logger.warning(f"Found {orphaned_count} orphaned video_progress records")

                # Delete orphaned records before adding constraint
                await conn.execute(text("""
                    DELETE FROM video_progress vp
                    WHERE NOT EXISTS (
                        SELECT 1 FROM users u WHERE u.id = vp.user_id
                    );
                """))
                logger.info(f"Deleted {orphaned_count} orphaned video_progress records")

            # Check if constraint already exists
            result = await conn.execute(text("""
                SELECT COUNT(*)
                FROM information_schema.table_constraints
                WHERE constraint_type = 'FOREIGN KEY'
                AND table_name = 'video_progress'
                AND constraint_name = 'video_progress_user_id_fkey';
            """))

            if result.scalar() == 0:
                # Add the foreign key constraint with CASCADE delete
                await conn.execute(text("""
                    ALTER TABLE video_progress
                    ADD CONSTRAINT video_progress_user_id_fkey
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
                """))
                logger.info("✓ Added foreign key constraint video_progress.user_id -> users.id")
            else:
                logger.info("- Foreign key constraint already exists, skipping")

        except Exception as e:
            logger.error(f"Failed to add foreign key constraint: {e}")
            raise

        logger.info("🎉 Foreign key constraint migration completed successfully!")


if __name__ == "__main__":
    import asyncio
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
