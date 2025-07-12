"""Automatic database migration runner."""

import asyncio
import logging
import os
from pathlib import Path

from sqlalchemy import text

from src.database.engine import engine


logger = logging.getLogger(__name__)


async def check_table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    AND table_name = :table_name
                )
            """),
            {"table_name": table_name},
        )
        return result.scalar()


async def check_migrations_table() -> bool:
    """Check if migrations tracking table exists."""
    return await check_table_exists("schema_migrations")


async def create_migrations_table() -> None:
    """Create table to track applied migrations."""
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    migration_name VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        )
        logger.info("Created schema_migrations table")


async def get_applied_migrations() -> list[str]:
    """Get list of already applied migrations."""
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT migration_name FROM schema_migrations ORDER BY applied_at"))
        return [row[0] for row in result.fetchall()]


async def mark_migration_applied(migration_name: str) -> None:
    """Mark a migration as applied."""
    async with engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO schema_migrations (migration_name) 
                VALUES (:name)
                ON CONFLICT (migration_name) DO NOTHING
            """),
            {"name": migration_name},
        )


async def run_migration(migration_path: Path) -> None:
    """Run a single migration file."""
    migration_name = migration_path.stem

    # Import and run the migration
    import importlib.util

    spec = importlib.util.spec_from_file_location(migration_name, migration_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Find the main migration function
    if hasattr(module, "main"):
        await module.main()
    else:
        # Look for a function with the migration name
        func_name = migration_name.replace("-", "_")
        if hasattr(module, func_name):
            await getattr(module, func_name)()
        else:
            logger.warning(f"No migration function found in {migration_path}")
            return

    # Mark as applied
    await mark_migration_applied(migration_name)
    logger.info(f"Applied migration: {migration_name}")


async def run_pending_migrations() -> None:
    """Run all pending migrations in order."""
    # Ensure migrations table exists
    if not await check_migrations_table():
        await create_migrations_table()

    # Get applied migrations
    applied = await get_applied_migrations()

    # Get migration files
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        logger.warning("No migrations directory found")
        return

    migration_files = sorted(migrations_dir.glob("*.py"))
    migration_files = [f for f in migration_files if not f.name.startswith("__")]

    # Run pending migrations
    for migration_file in migration_files:
        migration_name = migration_file.stem
        if migration_name not in applied:
            try:
                logger.info(f"Running migration: {migration_name}")
                await run_migration(migration_file)
            except Exception as e:
                logger.error(f"Failed to run migration {migration_name}: {e}")
                raise


async def ensure_rag_tables() -> None:
    """Ensure RAG tables exist with correct schema."""
    # Check if rag_document_chunks exists
    if not await check_table_exists("rag_document_chunks"):
        logger.info("Creating rag_document_chunks table...")

        # Get configured embedding dimensions
        embedding_dim = int(os.getenv("RAG_EMBEDDING_OUTPUT_DIM", "1024"))

        async with engine.begin() as conn:
            # Create the table with correct dimensions
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

            # Create indexes
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_id ON rag_document_chunks(doc_id)"))
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_doc_type ON rag_document_chunks(doc_type)")
            )
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_rag_chunks_metadata ON rag_document_chunks USING gin(metadata)")
            )

            # Only create vector indexes if we have embeddings
            if embedding_dim > 0:
                await conn.execute(
                    text("""
                    CREATE INDEX IF NOT EXISTS idx_rag_chunks_embedding_hnsw 
                    ON rag_document_chunks USING hnsw (embedding vector_cosine_ops)
                    WITH (m = 16, ef_construction = 64)
                """)
                )

            logger.info(f"Created rag_document_chunks table with {embedding_dim} dimensions")

    # Check chunk_processing_queue
    if not await check_table_exists("chunk_processing_queue"):
        logger.info("Creating chunk_processing_queue table...")

        async with engine.begin() as conn:
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

            # Create indexes
            await conn.execute(
                text("CREATE INDEX IF NOT EXISTS idx_chunk_queue_status ON chunk_processing_queue(status)")
            )
            await conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_chunk_queue_priority ON chunk_processing_queue(priority DESC, created_at ASC)"
                )
            )

            logger.info("Created chunk_processing_queue table")


async def run_auto_migrations() -> None:
    """Main entry point for automatic migrations."""
    try:
        logger.info("Starting automatic database migrations...")

        # Run any pending migrations
        await run_pending_migrations()

        # Ensure critical tables exist
        await ensure_rag_tables()

        logger.info("Database migrations completed successfully")

    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        # Don't raise - allow app to start but log the error
        # In production, you might want to fail fast instead


if __name__ == "__main__":
    # For testing
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_auto_migrations())
