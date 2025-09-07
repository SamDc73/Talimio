"""Rename roadmap_documents table to course_documents and roadmap_id to course_id."""

import asyncio
import logging

import asyncpg
from sqlalchemy import text

from src.database.migrations.base import get_connection_string

logger = logging.getLogger(__name__)


async def up():
    """Rename roadmap_documents to course_documents and roadmap_id to course_id."""
    conn_string = await get_connection_string()
    conn = await asyncpg.connect(conn_string)
    
    try:
        # Start transaction
        async with conn.transaction():
            # 1. Rename the table
            await conn.execute("ALTER TABLE IF EXISTS roadmap_documents RENAME TO course_documents")
            logger.info("Renamed table roadmap_documents to course_documents")
            
            # 2. Rename the roadmap_id column to course_id
            await conn.execute("ALTER TABLE course_documents RENAME COLUMN roadmap_id TO course_id")
            logger.info("Renamed column roadmap_id to course_id in course_documents table")
            
            # 3. Update the foreign key constraint name (optional but good for consistency)
            await conn.execute("""
                ALTER TABLE course_documents 
                DROP CONSTRAINT IF EXISTS roadmap_documents_roadmap_id_fkey
            """)
            
            await conn.execute("""
                ALTER TABLE course_documents 
                ADD CONSTRAINT course_documents_course_id_fkey 
                FOREIGN KEY (course_id) REFERENCES roadmaps(id) ON DELETE CASCADE
            """)
            logger.info("Updated foreign key constraint name")
            
            # 4. Update any indexes that might exist
            await conn.execute("DROP INDEX IF EXISTS idx_roadmap_documents_roadmap_id")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_course_documents_course_id ON course_documents(course_id)")
            logger.info("Updated indexes")
            
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        await conn.close()


async def down():
    """Revert the changes - rename back to roadmap_documents."""
    conn_string = await get_connection_string()
    conn = await asyncpg.connect(conn_string)
    
    try:
        async with conn.transaction():
            # Revert column name
            await conn.execute("ALTER TABLE course_documents RENAME COLUMN course_id TO roadmap_id")
            
            # Revert constraint
            await conn.execute("""
                ALTER TABLE course_documents 
                DROP CONSTRAINT IF EXISTS course_documents_course_id_fkey
            """)
            
            await conn.execute("""
                ALTER TABLE course_documents 
                ADD CONSTRAINT roadmap_documents_roadmap_id_fkey 
                FOREIGN KEY (roadmap_id) REFERENCES roadmaps(id) ON DELETE CASCADE
            """)
            
            # Revert indexes
            await conn.execute("DROP INDEX IF EXISTS idx_course_documents_course_id")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_roadmap_documents_roadmap_id ON roadmap_documents(roadmap_id)")
            
            # Revert table name
            await conn.execute("ALTER TABLE course_documents RENAME TO roadmap_documents")
            
        logger.info("Migration reverted successfully")
        
    except Exception as e:
        logger.error(f"Rollback failed: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "down":
        asyncio.run(down())
    else:
        asyncio.run(up())