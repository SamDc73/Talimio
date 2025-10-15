"""Create all necessary tables for the application."""

import asyncio
import logging
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import psycopg

from src.config.settings import get_settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """Create all tables needed for the application."""
    settings = get_settings()
    # Convert SQLAlchemy URL to psycopg format
    db_url = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
    # Connect directly using psycopg for DDL operations
    conn = await psycopg.AsyncConnection.connect(db_url)

    try:
        # Enable uuid-ossp extension
        await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
        logger.info("Enabled uuid-ossp extension")

        # Create videos table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                title VARCHAR(500) NOT NULL,
                description TEXT,
                channel VARCHAR(200),
                thumbnail_url TEXT,
                url TEXT,
                duration INTEGER,
                tags JSONB DEFAULT '[]'::jsonb,
                archived BOOLEAN DEFAULT FALSE,
                user_id UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created videos table")


        # Create books table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                title VARCHAR(500) NOT NULL,
                author VARCHAR(200),
                description TEXT,
                tags JSONB DEFAULT '[]'::jsonb,
                total_pages INTEGER,
                table_of_contents JSONB DEFAULT '[]'::jsonb,
                archived BOOLEAN DEFAULT FALSE,
                user_id UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created books table")

        # Removed: legacy book_progress table (unified on user_progress)

        # Create courses table (canonical)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id UUID NOT NULL,
                title VARCHAR(200) NOT NULL,
                description TEXT,
                tags TEXT,
                setup_commands TEXT,
                archived BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created courses table")

        # Create lessons table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS lessons (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                content TEXT NOT NULL,
                "order" INTEGER DEFAULT 0,
                module_name TEXT,
                module_order INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created lessons table")

        # Create course_documents table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS course_documents (
                id SERIAL PRIMARY KEY,
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                document_type VARCHAR(50),
                title VARCHAR(255) NOT NULL,
                file_path VARCHAR(500),
                source_url VARCHAR(500),
                crawl_date TIMESTAMP WITH TIME ZONE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP WITH TIME ZONE,
                embedded_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) DEFAULT 'pending'
            );
        """)
        logger.info("Created course_documents table")

        # Create unified user_progress table (replaces per-content progress tables)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS user_progress (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id UUID NOT NULL,
                content_id UUID NOT NULL,
                content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('book','video','course')),
                progress_percentage REAL NOT NULL DEFAULT 0,
                metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, content_id)
            );
        """)
        logger.info("Created user_progress table")

        # Create users table (minimal structure for now)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                email VARCHAR(255) UNIQUE NOT NULL,
                username VARCHAR(100) UNIQUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created users table")

        # Create ai_custom_instructions table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS ai_custom_instructions (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id UUID NOT NULL,
                instructions TEXT NOT NULL,
                context VARCHAR(100) DEFAULT 'global',
                context_id UUID,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, context, context_id)
            );
        """)
        logger.info("Created ai_custom_instructions table")

        # Create indexes for better query performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_books_user_id ON books(user_id);")
        # Indexes for courses and lessons
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_user_id ON courses(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_lessons_course_id ON lessons(course_id);")
        await conn.execute('CREATE INDEX IF NOT EXISTS idx_lessons_course_module_order ON lessons(course_id, module_order, "order");')
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_course_documents_course_id ON course_documents(course_id);")
        # Indexes for unified user_progress table
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_progress_user_id ON user_progress(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_progress_user_type ON user_progress(user_id, content_type);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_progress_content ON user_progress(content_id);")
        await conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_ai_custom_instructions_user_id ON ai_custom_instructions(user_id);"
        )
        logger.info("Created indexes")

        logger.info("All tables created successfully!")

    except Exception as e:
        logger.exception(f"Error creating tables: {e}")
        raise

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_tables())
