"""Fix missing embedding column in document_chunks table."""

import asyncio
import logging

from sqlalchemy import text

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_embedding_column() -> None:
    """Add missing embedding column to document_chunks table if it doesn't exist."""
    async with engine.begin() as conn:
        # First enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension enabled")

        # First check if the embedding column exists
        result = await conn.execute(
            text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'document_chunks' 
            AND column_name = 'embedding'
            """)
        )

        if not result.fetchone():
            logger.info("Adding missing embedding column to document_chunks table")

            # Add the embedding column
            await conn.execute(
                text("""
                ALTER TABLE document_chunks 
                ADD COLUMN embedding vector(1536)
                """)
            )

            logger.info("Successfully added embedding column")

            # Now create the HNSW index
            await conn.execute(
                text("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding 
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                """)
            )

            logger.info("Successfully created HNSW index on embedding column")
        else:
            logger.info("Embedding column already exists in document_chunks table")


async def main() -> None:
    """Run the migration."""
    try:
        await fix_embedding_column()
        logger.info("Embedding column fix migration completed successfully!")
    except Exception:
        logger.exception("Embedding column fix migration failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
