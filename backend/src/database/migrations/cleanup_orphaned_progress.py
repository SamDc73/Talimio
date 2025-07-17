"""Clean up orphaned progress records without user_id."""
import asyncio
import logging

import asyncpg

from src.config import env


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def cleanup_orphaned_progress():
    """Remove progress records without user_id."""
    database_url = env("DATABASE_URL")

    # Convert SQLAlchemy URL to asyncpg format
    if database_url.startswith("postgresql+asyncpg://"):
        database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

    conn = await asyncpg.connect(database_url)

    try:
        # Count orphaned records
        count = await conn.fetchval("""
            SELECT COUNT(*) FROM progress WHERE user_id IS NULL
        """)

        logger.info(f"Found {count} orphaned progress records without user_id")

        if count > 0:
            # Delete orphaned records
            deleted = await conn.execute("""
                DELETE FROM progress WHERE user_id IS NULL
            """)

            logger.info(f"Deleted {deleted} orphaned progress records")
        else:
            logger.info("No orphaned records to clean up")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(cleanup_orphaned_progress())
