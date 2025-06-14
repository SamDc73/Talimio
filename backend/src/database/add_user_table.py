"""Migration script to add User table for authentication."""

import asyncio
import logging

from sqlalchemy import text

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_user_table() -> None:
    """Add User table to the database."""
    async with engine.begin() as conn:
        # Create User table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(100) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """)
        )

        # Create indexes separately
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)"))

        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"))

        # Create trigger function separately
        await conn.execute(
            text("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql'
            """)
        )

        # Drop existing trigger
        await conn.execute(text("DROP TRIGGER IF EXISTS update_users_updated_at ON users"))

        # Create trigger
        await conn.execute(
            text("""
            CREATE TRIGGER update_users_updated_at
                BEFORE UPDATE ON users
                FOR EACH ROW
                EXECUTE FUNCTION update_updated_at_column()
            """)
        )

        logger.info("Successfully created User table")


async def main() -> None:
    """Run the migration."""
    try:
        await add_user_table()
        logger.info("Migration completed successfully!")
    except Exception:
        logger.exception("Migration failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
