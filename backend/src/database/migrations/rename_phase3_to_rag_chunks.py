#!/usr/bin/env python3
"""Rename phase3_document_chunks table to rag_document_chunks.

This migration renames the existing phase3_document_chunks table and its indexes
to use the more meaningful rag_document_chunks name.
"""

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


async def rename_phase3_to_rag_chunks() -> None:
    """Rename phase3_document_chunks table and indexes to rag_document_chunks."""
    async with engine.begin() as conn:
        logger.info("Starting table rename migration...")

        try:
            # Check if the old table exists
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'phase3_document_chunks'
                    )
                """)
            )
            old_table_exists = result.scalar()

            if not old_table_exists:
                logger.info("Table 'phase3_document_chunks' does not exist. Nothing to rename.")
                return

            # Check if the new table already exists
            result = await conn.execute(
                text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'rag_document_chunks'
                    )
                """)
            )
            new_table_exists = result.scalar()

            if new_table_exists:
                logger.warning("Table 'rag_document_chunks' already exists. Migration may have already been applied.")
                return

            # Rename the table
            await conn.execute(text("ALTER TABLE phase3_document_chunks RENAME TO rag_document_chunks"))
            logger.info("Renamed table from phase3_document_chunks to rag_document_chunks")

            # Rename indexes
            index_renames = [
                ("idx_phase3_chunks_doc_id", "idx_rag_chunks_doc_id"),
                ("idx_phase3_chunks_doc_type", "idx_rag_chunks_doc_type"),
                ("idx_phase3_chunks_metadata", "idx_rag_chunks_metadata"),
                ("idx_phase3_chunks_embedding_hnsw", "idx_rag_chunks_embedding_hnsw"),
                ("idx_phase3_chunks_embedding_ivfflat", "idx_rag_chunks_embedding_ivfflat"),
            ]

            for old_name, new_name in index_renames:
                try:
                    await conn.execute(text(f"ALTER INDEX IF EXISTS {old_name} RENAME TO {new_name}"))
                    logger.info(f"Renamed index from {old_name} to {new_name}")
                except Exception as e:
                    logger.warning(f"Could not rename index {old_name}: {e}")

            logger.info("Successfully completed table rename migration")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


async def main() -> None:
    """Run the migration."""
    try:
        await rename_phase3_to_rag_chunks()
        logger.info("Table rename migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
