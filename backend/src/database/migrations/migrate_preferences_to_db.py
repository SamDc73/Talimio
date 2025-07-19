"""Migration script to move existing JSON preference files to database."""

import asyncio
import json
import logging
from pathlib import Path
from uuid import UUID

from sqlalchemy import text

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Path to existing preference files
PREFERENCES_DIR = Path("data/preferences")


async def migrate_preferences_to_database() -> None:
    """Migrate existing JSON preference files to database."""
    if not PREFERENCES_DIR.exists():
        logger.info("No preferences directory found, skipping migration")
        return

    migrated_count = 0
    error_count = 0

    async with engine.begin() as conn:
        # Get all preference files
        preference_files = list(PREFERENCES_DIR.glob("*_preferences.json"))
        logger.info(f"Found {len(preference_files)} preference files to migrate")

        for pref_file in preference_files:
            try:
                # Extract user_id from filename (format: {user_id}_preferences.json)
                user_id_str = pref_file.stem.replace("_preferences", "")

                # Try to parse as UUID
                try:
                    user_id = UUID(user_id_str)
                except ValueError:
                    logger.warning(f"Skipping file {pref_file.name} - invalid UUID format")
                    continue

                # Load JSON data
                with pref_file.open() as f:
                    preferences_data = json.load(f)

                # Check if user exists in users table
                user_check = await conn.execute(
                    text("SELECT id FROM users WHERE id = :user_id"),
                    {"user_id": user_id}
                )
                if not user_check.fetchone():
                    logger.warning(f"User {user_id} not found in users table, skipping preferences")
                    continue

                # Check if preferences already exist in database
                existing_check = await conn.execute(
                    text("SELECT user_id FROM user_preferences WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                if existing_check.fetchone():
                    logger.info(f"Preferences for user {user_id} already exist in database, skipping")
                    continue

                # Insert preferences into database
                await conn.execute(
                    text("""
                    INSERT INTO user_preferences (user_id, preferences, created_at, updated_at)
                    VALUES (:user_id, :preferences, NOW(), NOW())
                    """),
                    {
                        "user_id": user_id,
                        "preferences": json.dumps(preferences_data)
                    }
                )

                migrated_count += 1
                logger.info(f"Migrated preferences for user {user_id}")

            except Exception as e:
                error_count += 1
                logger.error(f"Failed to migrate {pref_file.name}: {e}")
                continue

    logger.info(f"Migration completed: {migrated_count} migrated, {error_count} errors")


async def cleanup_preference_files() -> None:
    """Remove migrated preference files after successful migration."""
    if not PREFERENCES_DIR.exists():
        return

    async with engine.begin() as conn:
        preference_files = list(PREFERENCES_DIR.glob("*_preferences.json"))
        cleaned_count = 0

        for pref_file in preference_files:
            try:
                user_id_str = pref_file.stem.replace("_preferences", "")

                try:
                    user_id = UUID(user_id_str)
                except ValueError:
                    continue

                # Check if preferences exist in database
                db_check = await conn.execute(
                    text("SELECT user_id FROM user_preferences WHERE user_id = :user_id"),
                    {"user_id": user_id}
                )
                if db_check.fetchone():
                    # Preferences are in database, safe to remove file
                    pref_file.unlink()
                    cleaned_count += 1
                    logger.info(f"Removed migrated file: {pref_file.name}")

            except Exception as e:
                logger.error(f"Failed to cleanup {pref_file.name}: {e}")
                continue

        # Remove empty preferences directory if all files were cleaned up
        try:
            if cleaned_count > 0 and not any(PREFERENCES_DIR.iterdir()):
                PREFERENCES_DIR.rmdir()
                logger.info("Removed empty preferences directory")
        except OSError:
            pass  # Directory not empty or other issue

    logger.info(f"Cleanup completed: {cleaned_count} files removed")


async def main() -> None:
    """Run the migration."""
    try:
        logger.info("Starting preferences migration...")
        await migrate_preferences_to_database()

        # Ask user if they want to cleanup files
        response = input("Migration completed. Remove migrated JSON files? (y/N): ")
        if response.lower() in ("y", "yes"):
            await cleanup_preference_files()
        else:
            logger.info("Keeping original files. You can run cleanup manually later.")

    except Exception:
        logger.exception("Migration failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
