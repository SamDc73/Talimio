"""Add indexes and constraints to rag_document_chunks table."""

import asyncio
import logging

import asyncpg
from sqlalchemy import text

from src.config.settings import get_settings
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


async def check_existing_indexes():
    """Check what indexes already exist on the table."""
    async with async_session_maker() as session:
        result = await session.execute(
            text("""
                SELECT 
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = 'rag_document_chunks'
                ORDER BY indexname
            """)
        )

        indexes = result.fetchall()
        print("\n=== Existing indexes on rag_document_chunks ===")
        for idx in indexes:
            print(f"{idx.indexname}: {idx.indexdef}")

        return [idx.indexname for idx in indexes]


async def add_indexes():
    """Add performance indexes to rag_document_chunks table."""
    # Use raw asyncpg for DDL operations
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    try:
        existing_indexes = await check_existing_indexes()

        # Index 1: Composite index for doc_type and doc_id lookups
        if "idx_rag_chunks_doc_type_id" not in existing_indexes:
            print("\nCreating index: idx_rag_chunks_doc_type_id")
            await conn.execute("""
                CREATE INDEX CONCURRENTLY idx_rag_chunks_doc_type_id 
                ON rag_document_chunks(doc_type, doc_id)
            """)
            print("✓ Created idx_rag_chunks_doc_type_id")

        # Index 2: Index on doc_id for roadmap document lookups
        if "idx_rag_chunks_doc_id" not in existing_indexes:
            print("\nCreating index: idx_rag_chunks_doc_id")
            await conn.execute("""
                CREATE INDEX CONCURRENTLY idx_rag_chunks_doc_id 
                ON rag_document_chunks(doc_id)
            """)
            print("✓ Created idx_rag_chunks_doc_id")

        # Index 3: Index on roadmap_id in metadata for course documents
        if "idx_rag_chunks_roadmap_id" not in existing_indexes:
            print("\nCreating index: idx_rag_chunks_roadmap_id")
            await conn.execute("""
                CREATE INDEX CONCURRENTLY idx_rag_chunks_roadmap_id 
                ON rag_document_chunks((metadata->>'roadmap_id'))
                WHERE doc_type = 'course'
            """)
            print("✓ Created idx_rag_chunks_roadmap_id")

        # Index 4: Text search index for content
        if "idx_rag_chunks_content_text" not in existing_indexes:
            print("\nCreating text search index: idx_rag_chunks_content_text")
            await conn.execute("""
                CREATE INDEX CONCURRENTLY idx_rag_chunks_content_text 
                ON rag_document_chunks 
                USING gin(to_tsvector('english', content))
            """)
            print("✓ Created idx_rag_chunks_content_text")

        # Check if vector index exists (should already be there)
        if not any("embedding" in idx for idx in existing_indexes):
            print("\nCreating vector index: idx_rag_chunks_embedding")
            await conn.execute("""
                CREATE INDEX CONCURRENTLY idx_rag_chunks_embedding 
                ON rag_document_chunks 
                USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100)
            """)
            print("✓ Created idx_rag_chunks_embedding")

        print("\n✅ All indexes created successfully!")

        # Analyze the table to update statistics
        print("\nAnalyzing table to update statistics...")
        await conn.execute("ANALYZE rag_document_chunks")
        print("✓ Table analyzed")

    except Exception as e:
        logger.error(f"Error adding indexes: {e}")
        raise
    finally:
        await conn.close()


async def add_constraints():
    """Add any missing constraints to ensure data integrity."""
    settings = get_settings()
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    try:
        # Check existing constraints
        result = await conn.fetch("""
            SELECT 
                conname,
                contype
            FROM pg_constraint
            WHERE conrelid = 'rag_document_chunks'::regclass
        """)

        existing_constraints = [r["conname"] for r in result]
        print(f"\n=== Existing constraints: {existing_constraints} ===")

        # The table already has good constraints from the original migration
        # Just verify they exist
        required_constraints = [
            "rag_document_chunks_pkey",  # Primary key
            "rag_document_chunks_doc_type_check",  # doc_type validation
        ]

        for constraint in required_constraints:
            if constraint in existing_constraints:
                print(f"✓ Constraint {constraint} exists")
            else:
                print(f"⚠️  Missing constraint: {constraint}")

    except Exception as e:
        logger.error(f"Error checking constraints: {e}")
        raise
    finally:
        await conn.close()


async def main():
    """Run the index and constraint additions."""
    print("=== Phase 4: Schema Cleanup ===")

    # Add indexes
    await add_indexes()

    # Check constraints
    await add_constraints()

    print("\n✅ Phase 4 complete!")


if __name__ == "__main__":
    asyncio.run(main())
