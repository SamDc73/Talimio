#!/usr/bin/env python3
"""
Migration: Add pgvector column to memories table

This migration:
1. Ensures pgvector extension is enabled
2. Adds vector column for embeddings
3. Creates HNSW index for fast similarity search
4. Handles existing data gracefully
"""

import asyncio
import logging

from sqlalchemy import text

from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


async def upgrade():
    """Add pgvector support to learning_memories table."""
    async with async_session_maker() as session:
        try:
            # Enable pgvector extension
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            logger.info("✅ pgvector extension enabled")

            # Create clean_memories table (separate from old mem0 table)
            table_exists = await session.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = 'clean_memories'
                );
            """)
            )

            if not table_exists.scalar():
                # Create new clean table with proper structure
                await session.execute(
                    text("""
                    CREATE TABLE clean_memories (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        user_id UUID NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        embedding vector(1536)
                    );
                """)
                )
                logger.info("✅ Created clean_memories table with vector column")
            else:
                logger.info("✅ clean_memories table already exists")

            # Create HNSW index for fast similarity search
            index_exists = await session.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes 
                    WHERE tablename = 'clean_memories' 
                    AND indexname = 'clean_memories_embedding_hnsw_idx'
                );
            """)
            )

            if not index_exists.scalar():
                await session.execute(
                    text("""
                    CREATE INDEX clean_memories_embedding_hnsw_idx 
                    ON clean_memories 
                    USING hnsw (embedding vector_cosine_ops);
                """)
                )
                logger.info("✅ Created HNSW index for vector similarity search")

            # Create user index for efficient filtering
            user_index_exists = await session.execute(
                text("""
                SELECT EXISTS (
                    SELECT FROM pg_indexes 
                    WHERE tablename = 'clean_memories' 
                    AND indexname = 'clean_memories_user_id_idx'
                );
            """)
            )

            if not user_index_exists.scalar():
                await session.execute(
                    text("""
                    CREATE INDEX clean_memories_user_id_idx 
                    ON clean_memories (user_id);
                """)
                )
                logger.info("✅ Created user_id index for efficient filtering")

            await session.commit()
            logger.info("🎉 Migration completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Migration failed: {e}")
            raise


async def downgrade():
    """Remove clean_memories table and indexes."""
    async with async_session_maker() as session:
        try:
            # Drop the entire clean_memories table
            await session.execute(text("DROP TABLE IF EXISTS clean_memories CASCADE;"))

            await session.commit()
            logger.info("✅ Downgrade completed successfully")

        except Exception as e:
            await session.rollback()
            logger.error(f"❌ Downgrade failed: {e}")
            raise


if __name__ == "__main__":
    import asyncio

    # Set up logging
    logging.basicConfig(level=logging.INFO)

    # Load environment
    from dotenv import load_dotenv

    load_dotenv()

    print("🚀 Running pgvector migration for learning_memories table...")
    asyncio.run(upgrade())
    print("✅ Migration complete!")
