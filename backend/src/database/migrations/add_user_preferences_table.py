"""Migration script to add user_preferences table."""

import asyncio
import logging

from sqlalchemy import text

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_user_preferences_table() -> None:
    """Add user_preferences table to store user preferences in database instead of files."""
    async with engine.begin() as conn:
        # Create user_preferences table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS user_preferences (
                user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                preferences JSONB NOT NULL DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """)
        )

        # Create indexes for efficient queries
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)")
        )

        # Create GIN index for JSONB preferences for efficient queries on JSON fields
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_user_preferences_preferences ON user_preferences USING GIN (preferences)")
        )

        # Create trigger for updated_at
        await conn.execute(
            text("""
            CREATE TRIGGER update_user_preferences_updated_at
                BEFORE UPDATE ON user_preferences
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """)
        )

        logger.info("Successfully created user_preferences table")


async def main() -> None:
    """Run the migration."""
    try:
        await add_user_preferences_table()
        logger.info("User preferences table migration completed successfully!")
    except Exception:
        logger.exception("Migration failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
