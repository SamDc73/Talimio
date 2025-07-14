#!/usr/bin/env python3
"""Add support for multiple embedding versions."""

import asyncio
import logging
import sys
from pathlib import Path


# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text

from src.database.engine import engine


logger = logging.getLogger(__name__)


async def add_embedding_versions() -> None:
    """Add embedding versioning support."""
    async with engine.begin() as conn:
        # Create embedding models table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS embedding_models (
                id SERIAL PRIMARY KEY,
                model_name VARCHAR(255) NOT NULL,
                dimensions INTEGER NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                is_active BOOLEAN DEFAULT false,
                UNIQUE(model_name, dimensions)
            )
        """)
        )

        # Add embedding_model_id to chunks table
        await conn.execute(
            text("""
            ALTER TABLE rag_document_chunks 
            ADD COLUMN IF NOT EXISTS embedding_model_id INTEGER 
            REFERENCES embedding_models(id)
        """)
        )

        # Create index for efficient filtering
        await conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_chunks_embedding_model 
            ON rag_document_chunks(embedding_model_id)
        """)
        )

        logger.info("Added embedding versioning support")


async def main() -> None:
    """Run the migration."""
    try:
        await add_embedding_versions()
        logger.info("Embedding versions migration completed")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
