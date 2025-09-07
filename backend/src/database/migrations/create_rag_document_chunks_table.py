#!/usr/bin/env python3
"""
Migration: Create rag_document_chunks table with pgvector and useful indexes

- Ensures pgvector extension is enabled
- Creates rag_document_chunks with vector(embedding) column
- Adds uniqueness on (doc_id, chunk_index)
- Adds vector HNSW index, doc_type index, and course_id functional index

Run directly:
  python backend/src/database/migrations/create_rag_document_chunks_table.py
"""

import asyncio
import logging

from sqlalchemy import text

from src.config import env
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


async def upgrade():
    """Create rag_document_chunks table and indexes (idempotent)."""
    async with async_session_maker() as session:
        try:
            dims = int(env("RAG_EMBEDDING_OUTPUT_DIM", "1536"))

            # Enable pgvector extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("✅ pgvector extension ensured")

            # Create table
            await session.execute(
                text(
                    f"""
                    CREATE TABLE IF NOT EXISTS rag_document_chunks (
                        id BIGSERIAL PRIMARY KEY,
                        doc_id UUID NOT NULL,
                        doc_type TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        content TEXT NOT NULL,
                        embedding vector({dims}),
                        metadata JSONB,
                        created_at TIMESTAMPTZ DEFAULT NOW(),
                        updated_at TIMESTAMPTZ DEFAULT NOW()
                    );
                    """
                )
            )
            logger.info("✅ rag_document_chunks table ensured")

            # Uniqueness on (doc_id, chunk_index)
            await session.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes WHERE indexname = 'rag_document_chunks_doc_idx'
                        ) THEN
                            CREATE UNIQUE INDEX rag_document_chunks_doc_idx
                            ON rag_document_chunks (doc_id, chunk_index);
                        END IF;
                    END $$;
                    """
                )
            )
            logger.info("✅ Unique index on (doc_id, chunk_index) ensured")

            # Index on doc_type
            await session.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes WHERE indexname = 'rag_document_chunks_doc_type_idx'
                        ) THEN
                            CREATE INDEX rag_document_chunks_doc_type_idx
                            ON rag_document_chunks (doc_type);
                        END IF;
                    END $$;
                    """
                )
            )
            logger.info("✅ Index on doc_type ensured")

            # Functional index for course_id in metadata
            await session.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes WHERE indexname = 'rag_document_chunks_course_id_idx'
                        ) THEN
                            CREATE INDEX rag_document_chunks_course_id_idx
                            ON rag_document_chunks ((metadata->>'course_id'));
                        END IF;
                    END $$;
                    """
                )
            )
            logger.info("✅ Functional index on metadata->>'course_id' ensured")

            # HNSW index for vector similarity (cosine)
            await session.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_indexes WHERE indexname = 'rag_document_chunks_embedding_hnsw_idx'
                        ) THEN
                            CREATE INDEX rag_document_chunks_embedding_hnsw_idx
                            ON rag_document_chunks
                            USING hnsw (embedding vector_cosine_ops);
                        END IF;
                    END $$;
                    """
                )
            )
            logger.info("✅ HNSW vector index ensured")

            await session.commit()
            logger.info("🎉 Migration completed successfully")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise


async def downgrade():
    """Drop rag_document_chunks table and related indexes."""
    async with async_session_maker() as session:
        try:
            await session.execute(text("DROP TABLE IF EXISTS rag_document_chunks CASCADE;"))
            await session.commit()
            logger.info("✅ Downgrade completed successfully")
        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Downgrade failed: {e}")
            raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🚀 Running migration: create rag_document_chunks table...")
    asyncio.run(upgrade())
    print("✅ Migration complete!")
