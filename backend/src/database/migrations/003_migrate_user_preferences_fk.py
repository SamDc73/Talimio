"""Migrate user_preferences foreign key to reference profiles table.

This migration updates the user_preferences table to reference 
public.profiles instead of public.users, ensuring all authenticated
users can save preferences.
"""

import asyncio
import logging

import asyncpg

from src.config.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration - update foreign key to profiles table."""
    logger.info("Migrating user_preferences foreign key to profiles table...")

    # First, ensure all users in user_preferences have corresponding profiles
    await conn.execute("""
        INSERT INTO public.profiles (id)
        SELECT DISTINCT user_id FROM public.user_preferences
        ON CONFLICT (id) DO NOTHING
    """)

    # Drop the existing foreign key constraint
    await conn.execute("""
        ALTER TABLE public.user_preferences 
        DROP CONSTRAINT IF EXISTS user_preferences_user_id_fkey
    """)

    # Add new foreign key constraint referencing profiles
    await conn.execute("""
        ALTER TABLE public.user_preferences
        ADD CONSTRAINT user_preferences_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES public.profiles(id) ON DELETE CASCADE
    """)

    logger.info("Foreign key migrated successfully to profiles table")


async def down(conn: asyncpg.Connection) -> None:
    """Rollback migration - restore foreign key to users table."""
    logger.info("Rolling back user_preferences foreign key to users table...")

    # Drop the profiles foreign key constraint
    await conn.execute("""
        ALTER TABLE public.user_preferences 
        DROP CONSTRAINT IF EXISTS user_preferences_user_id_fkey
    """)

    # Restore foreign key constraint to users table
    await conn.execute("""
        ALTER TABLE public.user_preferences
        ADD CONSTRAINT user_preferences_user_id_fkey 
        FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE
    """)

    logger.info("Foreign key rolled back to users table")


async def main() -> None:
    """Run the migration."""
    # Connect to the database
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        # Apply the migration
        await up(conn)
        print("✅ Migration applied successfully: Migrated user_preferences FK to profiles")
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
