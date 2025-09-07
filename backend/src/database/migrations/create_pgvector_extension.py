#!/usr/bin/env python
"""Create pgvector extension and configure database for embeddings."""

import asyncio
import logging
from pathlib import Path

import asyncpg

# Get the path to the .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv

    load_dotenv(env_path)

from src.config.settings import get_settings

logger = logging.getLogger(__name__)


async def run_migration():
    """Run the migration to create pgvector extension."""
    settings = get_settings()
    
    # Convert the DATABASE_URL for asyncpg
    db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    
    conn = await asyncpg.connect(db_url)
    
    try:
        # Check if pgvector extension exists
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
        )
        
        if result == 0:
            # Create pgvector extension
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("Created pgvector extension")
        else:
            logger.info("pgvector extension already exists")
        
        # Set statement timeout for the session to avoid timeout issues
        await conn.execute("SET statement_timeout = '5min'")
        
        # Drop the old txtai_embeddings table if it exists (it might be in a bad state)
        await conn.execute("DROP TABLE IF EXISTS txtai_embeddings CASCADE")
        logger.info("Dropped old txtai_embeddings table if it existed")
        
        # Note: The new table 'course_document_embeddings' will be created automatically by txtai
        
        logger.info("✅ Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Error during migration: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())