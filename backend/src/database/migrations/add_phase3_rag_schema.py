#!/usr/bin/env python3
"""Add RAG system schema for context-aware document chunks.

This migration creates the enhanced schema for context-aware RAG,
supporting books, videos, and courses with intelligent chunking and metadata.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path


# Add the backend directory to the Python path
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from sqlalchemy import text

from src.database.engine import engine


logger = logging.getLogger(__name__)


async def add_phase3_rag_schema() -> None:
    """Add RAG system tables for context-aware document processing."""
    async with engine.begin() as conn:
        logger.info("Starting RAG schema migration...")

        # Get embedding dimensions from environment
        embedding_dim = int(os.getenv("RAG_EMBEDDING_OUTPUT_DIM", "1536"))
        logger.info(f"Creating RAG tables with {embedding_dim} dimensional embeddings")

        # Create enhanced RAG document chunks table
        await conn.execute(
            text(f"""
            CREATE TABLE IF NOT EXISTS rag_document_chunks (
                id SERIAL PRIMARY KEY,
                doc_id UUID NOT NULL,
                doc_type VARCHAR(20) NOT NULL CHECK (doc_type IN ('book', 'video', 'course')),
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector({embedding_dim}),
                metadata JSONB NOT NULL DEFAULT '{{}}',
                created_at TIMESTAMPTZ DEFAULT NOW(),
                
                -- Ensure unique chunks per document
                UNIQUE(doc_id, chunk_index)
            )
            """)
        )
        logger.info("Created rag_document_chunks table")

        # Create indexes for efficient querying
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_id ON rag_document_chunks(doc_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_type ON rag_document_chunks(doc_type)"))
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_metadata ON rag_document_chunks USING gin(metadata)")
        )

        # Create HNSW index for vector similarity search with appropriate parameters
        await conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw 
            ON rag_document_chunks USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
        """)
        )

        # Create IVFFlat index as alternative for better recall
        await conn.execute(
            text("""
            CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_ivfflat 
            ON rag_document_chunks USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        """)
        )

        logger.info("Created indexes for rag_document_chunks table")

        # Create chunk_processing_queue table for batch processing
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS chunk_processing_queue (
                id SERIAL PRIMARY KEY,
                doc_id UUID NOT NULL,
                doc_type VARCHAR(20) NOT NULL,
                status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
                priority INTEGER DEFAULT 5,
                metadata JSONB DEFAULT '{}',
                error_message TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                started_at TIMESTAMPTZ,
                completed_at TIMESTAMPTZ,
                
                -- Prevent duplicate queue entries
                UNIQUE(doc_id, doc_type)
            )
            """)
        )
        logger.info("Created chunk_processing_queue table")

        # Create indexes for processing queue
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_chunk_queue_status ON chunk_processing_queue(status)"))
        await conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_chunk_queue_priority ON chunk_processing_queue(priority DESC, created_at ASC)"
            )
        )

        logger.info("Successfully completed RAG schema migration")


async def main() -> None:
    """Run the migration."""
    try:
        await add_phase3_rag_schema()
        logger.info("RAG schema migration completed successfully")
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
