"""Enable pgvector extension and create txtai tables for Supabase."""

import asyncio
import logging

import asyncpg

logger = logging.getLogger(__name__)


async def run_migration() -> None:
    """Enable pgvector and prepare for txtai integration with Supabase."""
    import os
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        msg = "DATABASE_URL environment variable not set"
        raise ValueError(msg)
    
    # Connect to database
    conn = await asyncpg.connect(database_url)
    
    try:
        # Enable pgvector extension (Supabase has it pre-installed)
        logger.info("Enabling pgvector extension...")
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS vector;
        """)
        
        # Grant necessary permissions for txtai
        # txtai will create its own tables, but we ensure permissions are set
        logger.info("Setting up permissions for txtai...")
        await conn.execute("""
            -- Ensure current user has all necessary permissions
            GRANT USAGE ON SCHEMA public TO CURRENT_USER;
            GRANT CREATE ON SCHEMA public TO CURRENT_USER;
        """)
        
        # Create indexes for better performance
        # These will be on txtai-created tables
        logger.info("Preparing for txtai table creation...")
        
        # Note: txtai will create these tables automatically:
        # - txtai_embeddings (for vectors with pgvector backend)
        # - sections (for content with PostgreSQL content storage)
        # - objects (if object storage is enabled)
        
        # We just ensure the environment is ready
        logger.info("pgvector extension enabled and environment prepared for txtai")
        
        # Optional: Create a view for easier querying later
        await conn.execute("""
            -- Drop view if exists to allow re-running
            DROP VIEW IF EXISTS rag_search_view;
            
            -- This view will work once txtai creates its tables
            -- It provides a unified view of embeddings and content
            CREATE VIEW rag_search_view AS
            SELECT 
                s.id,
                s.text,
                s.tags,
                s.data,
                e.embedding
            FROM sections s
            LEFT JOIN txtai_embeddings e ON s.id = e.indexid
            WHERE s.id IS NOT NULL;
            
            COMMENT ON VIEW rag_search_view IS 'Unified view of txtai content and embeddings for RAG search';
        """)
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())