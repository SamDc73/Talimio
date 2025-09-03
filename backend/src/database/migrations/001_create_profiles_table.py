"""Create profiles table migration.

This migration creates a public.profiles table that references auth.users,
following Supabase best practices for user data.
"""

import asyncio
import logging

import asyncpg

from src.config.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration - create profiles table."""
    logger.info("Creating profiles table...")

    # Create profiles table
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS public.profiles (
            id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            username VARCHAR(100),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        )
    """)

    # Create index for faster lookups
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_profiles_id ON public.profiles(id)
    """)

    # Backfill profiles for existing auth.users
    await conn.execute("""
        INSERT INTO public.profiles (id)
        SELECT id FROM auth.users
        ON CONFLICT (id) DO NOTHING
    """)

    # Add table comment
    await conn.execute("""
        COMMENT ON TABLE public.profiles IS 
        'Public profile data for authenticated users - follows Supabase best practices'
    """)

    logger.info("Profiles table created successfully")


async def down(conn: asyncpg.Connection) -> None:
    """Rollback migration - drop profiles table."""
    logger.info("Dropping profiles table...")

    # Drop the table (cascade will handle dependencies)
    await conn.execute("""
        DROP TABLE IF EXISTS public.profiles CASCADE
    """)

    logger.info("Profiles table dropped successfully")


async def main() -> None:
    """Run the migration."""
    # Connect to the database
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        # Apply the migration
        await up(conn)
        print("✅ Migration applied successfully: Created profiles table")
    except Exception as e:
        logger.exception("Migration failed")
        print(f"❌ Migration failed: {e}")
        # Optionally rollback
        # await down(conn)
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
