"""Create txtai embeddings tables for pgvector storage."""

import asyncio
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger(__name__)


async def up(conn: AsyncConnection) -> None:
    """Create txtai tables with proper async execution."""
    # Create embeddings table for txtai with pgvector
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS txtai_embeddings (
            id TEXT PRIMARY KEY,
            data JSONB NOT NULL,
            tags TEXT,
            entry JSONB,
            embeddings vector(384)
        )
    """)
    
    # Create HNSW index for fast similarity search
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txtai_embeddings_vector
        ON txtai_embeddings USING hnsw (embeddings vector_cosine_ops)
    """)
    
    # Create GIN index for JSONB data search
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txtai_embeddings_data
        ON txtai_embeddings USING gin(data)
    """)
    
    # Create index on tags for filtering
    await conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txtai_embeddings_tags
        ON txtai_embeddings (tags)
    """)


async def down(conn: AsyncConnection) -> None:
    """Drop txtai tables."""
    await conn.execute("DROP TABLE IF EXISTS txtai_embeddings CASCADE")


async def run() -> None:
    """Run migration standalone."""
    from src.database.session import async_session_maker
    
    async with async_session_maker() as session:
        try:
            # Create embeddings table for txtai with pgvector
            await session.execute(text("""
                CREATE TABLE IF NOT EXISTS txtai_embeddings (
                    id TEXT PRIMARY KEY,
                    data JSONB NOT NULL,
                    tags TEXT,
                    entry JSONB,
                    embeddings vector(384)
                )
            """))
            
            # Create HNSW index for fast similarity search
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_txtai_embeddings_vector
                ON txtai_embeddings USING hnsw (embeddings vector_cosine_ops)
            """))
            
            # Create GIN index for JSONB data search
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_txtai_embeddings_data
                ON txtai_embeddings USING gin(data)
            """))
            
            # Create index on tags for filtering
            await session.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_txtai_embeddings_tags
                ON txtai_embeddings (tags)
            """))
            
            await session.commit()
            logger.info("✅ Migration completed successfully")
            
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise


if __name__ == "__main__":
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    print("🚀 Running txtai embeddings table migration...")
    asyncio.run(run())
    print("✅ Migration complete!")