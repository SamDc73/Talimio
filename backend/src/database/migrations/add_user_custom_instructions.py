"""Add user custom instructions table for AI personalization."""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.settings import get_settings


logger = logging.getLogger(__name__)


async def add_user_custom_instructions_table():
    """Create user_custom_instructions table for AI personalization."""
    settings = get_settings()
    engine = create_async_engine(settings.DATABASE_URL, echo=True)

    async with engine.begin() as conn:
        try:
            # Create the table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_custom_instructions (
                    user_id UUID PRIMARY KEY,
                    instructions TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))

            logger.info("Created user_custom_instructions table")

            # Create index on user_id for faster lookups
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_custom_instructions_user_id 
                ON user_custom_instructions(user_id)
            """))

            logger.info("Created index on user_custom_instructions")

            # Create trigger to update updated_at
            await conn.execute(text("""
                CREATE OR REPLACE FUNCTION update_updated_at_column()
                RETURNS TRIGGER AS $$
                BEGIN
                    NEW.updated_at = NOW();
                    RETURN NEW;
                END;
                $$ language 'plpgsql'
            """))

            await conn.execute(text("""
                DROP TRIGGER IF EXISTS update_user_custom_instructions_updated_at 
                ON user_custom_instructions
            """))

            await conn.execute(text("""
                CREATE TRIGGER update_user_custom_instructions_updated_at
                    BEFORE UPDATE ON user_custom_instructions
                    FOR EACH ROW
                    EXECUTE FUNCTION update_updated_at_column()
            """))

            logger.info("Created update trigger for user_custom_instructions")

        except Exception as e:
            logger.error(f"Failed to create user_custom_instructions table: {e}")
            raise

    await engine.dispose()


async def run_migration(engine: AsyncEngine):
    """Run the migration using the provided engine."""
    async with engine.begin() as conn:
        try:
            # Create the table
            await conn.execute(text("""
                CREATE TABLE IF NOT EXISTS user_custom_instructions (
                    user_id UUID PRIMARY KEY,
                    instructions TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """))

            logger.info("Created user_custom_instructions table")

            # Create index on user_id for faster lookups
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_user_custom_instructions_user_id 
                ON user_custom_instructions(user_id)
            """))

            logger.info("Created index on user_custom_instructions")

        except Exception as e:
            logger.error(f"Failed to create user_custom_instructions table: {e}")
            raise
