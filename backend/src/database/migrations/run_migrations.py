"""Run all database migrations for the phantom users fix.

This script runs all migrations in order to set up the profiles
table and fix the phantom users issue.
"""

import asyncio
import logging
import sys
from pathlib import Path

import asyncpg

from src.config.settings import get_settings


# Add backend to path to import migrations
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

settings = get_settings()


async def run_all_migrations() -> None:
    """Run all migrations in order."""
    # Import migration modules directly
    import importlib.util

    # Load migration modules dynamically
    migrations_dir = Path(__file__).parent

    def load_migration(filename):
        spec = importlib.util.spec_from_file_location(
            filename.stem,
            migrations_dir / filename
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    migration_files = [
        "001_create_profiles_table.py",
        "002_create_profile_trigger.py",
        "003_migrate_user_preferences_fk.py",
    ]

    migrations = []
    for filename in migration_files:
        filepath = Path(filename)
        if (migrations_dir / filepath).exists():
            module = load_migration(filepath)
            migrations.append((filepath.stem, module))

    # Connect to database
    conn = await asyncpg.connect(settings.DATABASE_URL)

    try:
        for name, module in migrations:
            logger.info(f"\n🔄 Running migration: {name}")
            try:
                await module.up(conn)
                logger.info(f"✅ Migration {name} completed successfully")
            except Exception as e:
                logger.error(f"❌ Migration {name} failed: {e}")
                raise

        logger.info("\n🎉 All migrations completed successfully!")

        # Verify the setup
        logger.info("\n🔍 Verifying migration results...")

        # Check profiles table exists
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'profiles'
            )
        """)
        logger.info(f"✓ Profiles table exists: {result}")

        # Check trigger exists
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.triggers 
                WHERE trigger_name = 'on_auth_user_created'
            )
        """)
        logger.info(f"✓ Auto-creation trigger exists: {result}")

        # Count profiles
        profile_count = await conn.fetchval("SELECT COUNT(*) FROM public.profiles")
        auth_user_count = await conn.fetchval("SELECT COUNT(*) FROM auth.users")
        logger.info(f"✓ Profiles created: {profile_count}/{auth_user_count}")

        # Check foreign key
        result = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.table_constraints 
                WHERE constraint_name = 'user_preferences_user_id_fkey'
                AND table_name = 'user_preferences'
            )
        """)
        logger.info(f"✓ User preferences FK updated: {result}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_all_migrations())
