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
                uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
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

        # Create book_progress table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS book_progress (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                user_id UUID NOT NULL,
                current_page INTEGER DEFAULT 1,
                toc_progress JSONB DEFAULT '{}'::jsonb,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, user_id)
            );
        """)
        logger.info("Created book_progress table")

        # Create roadmaps table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS roadmaps (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                title VARCHAR(500) NOT NULL,
                description TEXT,
                tags JSONB DEFAULT '[]'::jsonb,
                archived BOOLEAN DEFAULT FALSE,
                user_id UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created roadmaps table")

        # Create course_prompts table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS course_prompts (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                roadmap_id UUID REFERENCES roadmaps(id) ON DELETE CASCADE,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                prompt TEXT NOT NULL,
                preferences JSONB DEFAULT '{}'::jsonb,
                user_id UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created course_prompts table")

        # Create courses table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                roadmap_id UUID REFERENCES roadmaps(id) ON DELETE CASCADE,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                modules JSONB DEFAULT '[]'::jsonb,
                toc_tree JSONB DEFAULT '[]'::jsonb,
                topic TEXT,
                difficulty VARCHAR(50),
                tags JSONB DEFAULT '[]'::jsonb,
                archived BOOLEAN DEFAULT FALSE,
                user_id UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created courses table")

        # Create course_progress table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS course_progress (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
                user_id UUID NOT NULL,
                completed_lessons JSONB DEFAULT '[]'::jsonb,
                quiz_scores JSONB DEFAULT '{}'::jsonb,
                last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(course_id, user_id)
            );
        """)
        logger.info("Created course_progress table")

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
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_book_progress_user_id ON book_progress(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON roadmaps(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_course_prompts_user_id ON course_prompts(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_courses_user_id ON courses(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_course_progress_user_id ON course_progress(user_id);")
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
