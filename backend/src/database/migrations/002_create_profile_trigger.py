"""Create trigger for auto-creating profiles on user signup.

This migration creates a PostgreSQL trigger that automatically creates
a profile record whenever a new user is created in auth.users.
"""

import asyncio
import logging

import asyncpg

from src.config.settings import get_settings


logger = logging.getLogger(__name__)
settings = get_settings()


async def up(conn: asyncpg.Connection) -> None:
    """Apply migration - create profile auto-creation trigger."""
    logger.info("Creating profile auto-creation trigger...")

    # Create the trigger function
    await conn.execute("""
        CREATE OR REPLACE FUNCTION public.handle_new_user() 
        RETURNS TRIGGER AS $$
        BEGIN
            INSERT INTO public.profiles (id, created_at, updated_at)
            VALUES (NEW.id, NOW(), NOW())
            ON CONFLICT (id) DO NOTHING;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER
    """)

    # Create the trigger on auth.users table
    await conn.execute("""
        CREATE TRIGGER on_auth_user_created
        AFTER INSERT ON auth.users
        FOR EACH ROW 
        EXECUTE FUNCTION public.handle_new_user()
    """)

    logger.info("Profile auto-creation trigger created successfully")


async def down(conn: asyncpg.Connection) -> None:
    """Rollback migration - drop trigger and function."""
    logger.info("Dropping profile auto-creation trigger...")

    # Drop the trigger
    await conn.execute("""
        DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users
    """)

    # Drop the function
    await conn.execute("""
        DROP FUNCTION IF EXISTS public.handle_new_user()
    """)

    logger.info("Profile auto-creation trigger dropped successfully")


async def main() -> None:
    """Run the migration."""
    # Connect to the database
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        # Apply the migration
        await up(conn)
        print("✅ Migration applied successfully: Created profile auto-creation trigger")
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
