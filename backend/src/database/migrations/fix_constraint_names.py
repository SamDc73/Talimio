#!/usr/bin/env python3
"""Fix remaining constraint names after table rename."""

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


async def fix_constraint_names() -> None:
    """Rename remaining constraints that still have old naming."""
    async with engine.begin() as conn:
        logger.info("Fixing constraint names...")

        try:
            # Rename primary key constraint
            await conn.execute(
                text("ALTER TABLE rag_document_chunks RENAME CONSTRAINT phase3_document_chunks_pkey TO rag_document_chunks_pkey")
            )
            logger.info("Renamed primary key constraint")

            # Rename unique constraint
            await conn.execute(
                text("ALTER TABLE rag_document_chunks RENAME CONSTRAINT phase3_document_chunks_doc_id_chunk_index_key TO rag_document_chunks_doc_id_chunk_index_key")
            )
            logger.info("Renamed unique constraint")

            logger.info("Successfully fixed all constraint names")

        except Exception as e:
            logger.warning(f"Some constraints may already be renamed or don't exist: {e}")


async def main() -> None:
    """Run the migration."""
    try:
        await fix_constraint_names()
        logger.info("Constraint name fixes completed")
    except Exception as e:
        logger.error(f"Migration failed: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
