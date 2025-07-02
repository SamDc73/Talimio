"""Migration script to add RAG system tables and pgvector extension."""

import asyncio
import logging

from sqlalchemy import text

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def add_rag_system() -> None:
    """Add RAG system tables and pgvector extension to the database."""
    async with engine.begin() as conn:
        # Enable pgvector extension FIRST - this is critical
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")
        except Exception as e:
            logger.error(f"Failed to create pgvector extension: {e}")
            raise

        # Extend roadmaps table with RAG support
        await conn.execute(
            text("""
            ALTER TABLE roadmaps
            ADD COLUMN IF NOT EXISTS rag_enabled BOOLEAN DEFAULT FALSE
            """)
        )
        logger.info("Added rag_enabled column to roadmaps table")

        # Create roadmap_documents table
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS roadmap_documents (
                id SERIAL PRIMARY KEY,
                roadmap_id UUID REFERENCES roadmaps(id) ON DELETE CASCADE,
                document_type VARCHAR(20) NOT NULL,
                title VARCHAR(255) NOT NULL,
                file_path VARCHAR(500),
                url VARCHAR(500),
                source_url VARCHAR(500),
                crawl_date TIMESTAMPTZ,
                content_hash VARCHAR(64),
                parsed_content TEXT,
                doc_metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                processed_at TIMESTAMPTZ,
                embedded_at TIMESTAMPTZ,
                status VARCHAR(20) DEFAULT 'pending'
            )
            """)
        )
        logger.info("Created roadmap_documents table")

        # Create document_chunks table with vector column
        await conn.execute(
            text("""
            CREATE TABLE IF NOT EXISTS document_chunks (
                id SERIAL PRIMARY KEY,
                document_id INTEGER REFERENCES roadmap_documents(id) ON DELETE CASCADE,
                node_id VARCHAR(255) UNIQUE NOT NULL,
                chunk_index INTEGER NOT NULL,
                content TEXT NOT NULL,
                embedding vector(1536),
                token_count INTEGER,
                doc_metadata JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """)
        )
        logger.info("Created document_chunks table")

        # Create indexes for roadmap_documents
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_roadmap_documents_roadmap_id ON roadmap_documents(roadmap_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_roadmap_documents_status ON roadmap_documents(status)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_roadmap_documents_content_hash ON roadmap_documents(content_hash)"))

        # Create indexes for document_chunks
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_document_chunks_document_id ON document_chunks(document_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_document_chunks_node_id ON document_chunks(node_id)"))

        # Create HNSW index for vector similarity search
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding ON document_chunks USING hnsw (embedding vector_cosine_ops)"))

        logger.info("Successfully created RAG system tables and indexes")


async def main() -> None:
    """Run the migration."""
    try:
        await add_rag_system()
        logger.info("RAG system migration completed successfully!")
    except Exception:
        logger.exception("RAG system migration failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
