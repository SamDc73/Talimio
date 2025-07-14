#!/usr/bin/env python3
"""Migrate all data from document_chunks to rag_document_chunks.

This migration copies all course documents from the old RAG system to the new one.
It preserves all data including embeddings and metadata.
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


async def migrate_document_chunks_to_rag() -> None:
    """Migrate all data from document_chunks to rag_document_chunks."""
    async with engine.begin() as conn:
        logger.info("Starting document chunks migration...")

        try:
            # 0. Ensure UUID extension is available
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))

            # 1. Check how many chunks we have in the old table
            result = await conn.execute(text("""
                SELECT COUNT(*) as count FROM document_chunks
            """))
            old_count = result.scalar()
            logger.info(f"Found {old_count} chunks in document_chunks table")

            # 2. Check current state of new table
            result = await conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM rag_document_chunks 
                WHERE doc_type = 'course'
            """))
            existing_doc_count = result.scalar()
            logger.info(f"Found {existing_doc_count} document type chunks in rag_document_chunks")

            if existing_doc_count > 0:
                logger.warning("Migration may have already been run. Checking for duplicates...")

                # Check if we have any matching document IDs
                result = await conn.execute(text("""
                    SELECT COUNT(DISTINCT dc.document_id) as count
                    FROM document_chunks dc
                    WHERE EXISTS (
                        SELECT 1 FROM rag_document_chunks rdc
                        WHERE rdc.doc_id = dc.document_id
                        AND rdc.doc_type = 'document'
                    )
                """))
                duplicate_count = result.scalar()

                if duplicate_count > 0:
                    logger.error(f"Found {duplicate_count} documents already migrated. Aborting to prevent duplicates.")
                    return

            # 3. Perform the migration
            logger.info("Migrating document chunks...")

            # Insert all chunks from old table to new table
            # Generate a UUID based on the integer document_id for consistency
            await conn.execute(text("""
                INSERT INTO rag_document_chunks (
                    doc_id,
                    doc_type,
                    chunk_index,
                    content,
                    embedding,
                    metadata,
                    created_at
                )
                SELECT 
                    -- Generate deterministic UUID from document_id
                    uuid_generate_v5('6ba7b810-9dad-11d1-80b4-00c04fd430c8'::uuid, 'document_' || dc.document_id::text) as doc_id,
                    'course' as doc_type,
                    dc.chunk_index,
                    dc.content,
                    dc.embedding,
                    JSONB_BUILD_OBJECT(
                        'original_document_id', dc.document_id,
                        'roadmap_id', rd.roadmap_id,
                        'document_title', rd.title,
                        'document_type', rd.document_type
                    ) || COALESCE(dc.metadata, '{}'::jsonb) as metadata,
                    dc.created_at
                FROM document_chunks dc
                JOIN roadmap_documents rd ON dc.document_id = rd.id
                WHERE dc.embedding IS NOT NULL  -- Only migrate chunks with embeddings
            """))

            # 4. Verify migration
            result = await conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM rag_document_chunks 
                WHERE doc_type = 'course'
            """))
            new_count = result.scalar()

            # Get count of chunks with embeddings in old table
            result = await conn.execute(text("""
                SELECT COUNT(*) as count 
                FROM document_chunks 
                WHERE embedding IS NOT NULL
            """))
            old_with_embeddings = result.scalar()

            logger.info("Migration complete:")
            logger.info(f"  - Chunks in old table: {old_count}")
            logger.info(f"  - Chunks with embeddings in old table: {old_with_embeddings}")
            logger.info(f"  - Document chunks in new table: {new_count}")

            if new_count == old_with_embeddings:
                logger.info("✓ All chunks with embeddings successfully migrated!")
            else:
                logger.warning(f"⚠ Migration count mismatch: expected {old_with_embeddings}, got {new_count}")

            # 5. Create indexes for better performance
            logger.info("Creating indexes for migrated data...")

            # Index on (doc_type, doc_id) for document retrieval
            await conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_type_id 
                ON rag_document_chunks(doc_type, doc_id)
                WHERE doc_type = 'course'
            """))

            logger.info("Migration completed successfully!")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            raise


async def rollback_migration() -> None:
    """Rollback the migration by removing migrated document chunks."""
    async with engine.begin() as conn:
        logger.info("Rolling back document chunks migration...")

        try:
            # Delete only the document type chunks we migrated
            result = await conn.execute(text("""
                DELETE FROM rag_document_chunks 
                WHERE doc_type = 'course'
            """))

            deleted_count = result.rowcount
            logger.info(f"Removed {deleted_count} migrated document chunks")

            # Drop the index we created
            await conn.execute(text("""
                DROP INDEX IF EXISTS idx_rag_chunks_doc_type_id
            """))

            logger.info("Rollback completed successfully!")

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            raise


async def main() -> None:
    """Run the migration with optional rollback."""
    import argparse

    parser = argparse.ArgumentParser(description="Migrate document chunks to new RAG table")
    parser.add_argument("--rollback", action="store_true", help="Rollback the migration")
    args = parser.parse_args()

    try:
        if args.rollback:
            await rollback_migration()
        else:
            await migrate_document_chunks_to_rag()
    except Exception as e:
        logger.error(f"Operation failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
