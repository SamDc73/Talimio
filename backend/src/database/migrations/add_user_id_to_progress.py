"""Add user_id column to progress table for user-specific tracking."""
import asyncio
import logging

import asyncpg

from src.config import env


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_user_id_to_progress():
    """Add user_id column to progress table."""
    database_url = env("DATABASE_URL")

    # Convert SQLAlchemy URL to asyncpg format
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(database_url)

    try:
        # Check if user_id column already exists
        column_exists = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.columns 
                WHERE table_name = 'progress' 
                AND column_name = 'user_id'
            )
        """)

        if column_exists:
            logger.info("user_id column already exists in progress table")
            return

        logger.info("Adding user_id column to progress table...")

        # Add user_id column (nullable initially)
        await conn.execute("""
            ALTER TABLE progress 
            ADD COLUMN user_id UUID
        """)

        logger.info("Added user_id column")

        # Create index for better query performance
        await conn.execute("""
            CREATE INDEX idx_progress_user_lesson 
            ON progress(user_id, lesson_id)
        """)

        logger.info("Created index on (user_id, lesson_id)")

        # Add foreign key constraint to users table
        await conn.execute("""
            ALTER TABLE progress 
            ADD CONSTRAINT fk_progress_user 
            FOREIGN KEY (user_id) 
            REFERENCES users(id) 
            ON DELETE CASCADE
        """)

        logger.info("Added foreign key constraint to users table")

        # Update the unique constraint to include user_id
        # First drop the existing constraint if it exists
        await conn.execute("""
            ALTER TABLE progress 
            DROP CONSTRAINT IF EXISTS unique_user_lesson_progress
        """)

        # Create new unique constraint
        await conn.execute("""
            ALTER TABLE progress 
            ADD CONSTRAINT unique_user_lesson_progress 
            UNIQUE (user_id, lesson_id, course_id)
        """)

        logger.info("Updated unique constraint to include user_id")

        logger.info("Migration completed successfully!")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(add_user_id_to_progress())
