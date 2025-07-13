#!/usr/bin/env python3
"""Fix document_chunks table to use 768 dimensions for Ollama embeddings."""

import asyncio
import logging
import sys
from pathlib import Path


# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text

from src.config import env
from src.database.engine import engine


logger = logging.getLogger(__name__)


async def fix_document_chunks_dimensions() -> None:
    """Fix document_chunks table to use 768 dimensions."""
    async with engine.begin() as conn:
        logger.info("Starting document_chunks dimension fix...")

        # Get current dimension from environment
        embedding_dim = int(env("RAG_EMBEDDING_OUTPUT_DIM", "768"))
        logger.info(f"Target embedding dimension: {embedding_dim}")

        # First, check if document_chunks has any data
        result = await conn.execute(
            text("SELECT COUNT(*) FROM document_chunks WHERE embedding IS NOT NULL")
        )
        existing_count = result.scalar()

        if existing_count > 0:
            logger.warning(f"Found {existing_count} existing embeddings in document_chunks. These will be removed.")

            # Clear existing embeddings since they have wrong dimensions
            await conn.execute(
                text("UPDATE document_chunks SET embedding = NULL")
            )
            logger.info("Cleared existing embeddings")

        # Drop the existing embedding column
        await conn.execute(
            text("ALTER TABLE document_chunks DROP COLUMN IF EXISTS embedding")
        )
        logger.info("Dropped existing embedding column")

        # Add new embedding column with correct dimensions
        await conn.execute(
            text(f"ALTER TABLE document_chunks ADD COLUMN embedding vector({embedding_dim})")
        )
        logger.info(f"Added new embedding column with {embedding_dim} dimensions")

        # Recreate indexes for the embedding column
        await conn.execute(
            text("""
                CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_hnsw 
                ON document_chunks USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
            """)
        )
        logger.info("Created HNSW index for document_chunks")

        logger.info("Successfully fixed document_chunks dimensions")


async def main() -> None:
    """Run the migration."""
    try:
        await fix_document_chunks_dimensions()
        logger.info("Migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
