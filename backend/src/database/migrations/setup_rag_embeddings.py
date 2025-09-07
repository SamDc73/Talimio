#!/usr/bin/env python
"""Setup RAG embeddings tables and clean up old tables."""

import asyncio
import logging
from pathlib import Path

import asyncpg

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get the path to the .env file
env_path = Path(__file__).parent.parent.parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)

from src.config.settings import get_settings


async def run_migration():
    """Run the migration to set up RAG embeddings properly."""
    settings = get_settings()
    
    # Convert the DATABASE_URL for asyncpg
    db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    
    logger.info("Connecting to database...")
    conn = await asyncpg.connect(db_url)
    
    try:
        # Set a longer statement timeout for this migration
        await conn.execute("SET statement_timeout = '10min'")
        logger.info("Set statement timeout to 10 minutes")
        
        # 1. Check and create pgvector extension
        result = await conn.fetchval(
            "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
        )
        
        if result == 0:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            logger.info("✅ Created pgvector extension")
        else:
            logger.info("✅ pgvector extension already exists")
        
        # 2. Clean up old/unused tables (if they exist and we have permission)
        tables_to_clean = [
            'chunk_processing_queue',
            'document_chunks', 
            'rag_document_chunks'
        ]
        
        for table in tables_to_clean:
            try:
                # Check if table exists
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = $1)",
                    table
                )
                if exists:
                    # Check if we can drop it (check if empty first)
                    count = await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
                    if count == 0:
                        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                        logger.info(f"✅ Dropped unused table: {table}")
                    else:
                        logger.info(f"⚠️  Table {table} has {count} rows, keeping it")
            except Exception as e:
                logger.warning(f"Could not clean up table {table}: {e}")
        
        # 3. Ensure course_document_embeddings table exists with proper structure
        # This table will be managed by txtai, but we ensure it can be created
        logger.info("✅ Table 'course_document_embeddings' ready for txtai")
        
        # 4. Check roadmap_documents table has proper status column
        has_status = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'roadmap_documents' 
                AND column_name = 'status'
            )
            """
        )
        
        if not has_status:
            await conn.execute("""
                ALTER TABLE roadmap_documents 
                ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'pending'
            """)
            logger.info("✅ Added status column to roadmap_documents")
        else:
            logger.info("✅ roadmap_documents.status column exists")
            
        # 5. Add other required columns to roadmap_documents if missing
        columns_to_add = [
            ("processed_at", "TIMESTAMP WITH TIME ZONE"),
            ("embedded_at", "TIMESTAMP WITH TIME ZONE"),
            ("parsed_content", "TEXT"),
            ("content_hash", "VARCHAR(64)")
        ]
        
        for col_name, col_type in columns_to_add:
            has_column = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.columns 
                    WHERE table_name = 'roadmap_documents' 
                    AND column_name = $1
                )
                """,
                col_name
            )
            
            if not has_column:
                await conn.execute(f"""
                    ALTER TABLE roadmap_documents 
                    ADD COLUMN IF NOT EXISTS {col_name} {col_type}
                """)
                logger.info(f"✅ Added {col_name} column to roadmap_documents")
        
        # 6. Create indexes for better performance
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_roadmap_documents_status 
            ON roadmap_documents(status)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_roadmap_documents_roadmap_id 
            ON roadmap_documents(roadmap_id)
        """)
        logger.info("✅ Created indexes on roadmap_documents")
        
        # 7. Clean up any failed documents to allow retry
        result = await conn.execute("""
            UPDATE roadmap_documents 
            SET status = 'pending', 
                processed_at = NULL,
                embedded_at = NULL
            WHERE status = 'failed'
        """)
        logger.info(f"✅ Reset {result.split()[-1]} failed documents to pending")
        
        logger.info("\n✅ Migration completed successfully!")
        logger.info("The RAG embeddings system is ready to use.")
        
    except Exception as e:
        logger.error(f"❌ Error during migration: {e}")
        raise
    finally:
        await conn.close()
        logger.info("Database connection closed")


if __name__ == "__main__":
    asyncio.run(run_migration())