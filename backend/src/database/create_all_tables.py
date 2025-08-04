"""Create all necessary tables for the application."""

import asyncio
import logging
import sys
from pathlib import Path


sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

import asyncpg

from src.config.settings import get_settings


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def create_tables() -> None:
    """Create all tables needed for the application."""
    settings = get_settings()
    # Convert SQLAlchemy URL to asyncpg format
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    # Connect directly using asyncpg for DDL operations
    conn = await asyncpg.connect(db_url)

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

        # Create flashcard_decks table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flashcard_decks (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                name VARCHAR(200) NOT NULL,
                description TEXT,
                tags JSONB DEFAULT '[]'::jsonb,
                archived BOOLEAN DEFAULT FALSE,
                user_id UUID NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created flashcard_decks table")

        # Create flashcard_cards table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS flashcard_cards (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                deck_id UUID NOT NULL REFERENCES flashcard_decks(id) ON DELETE CASCADE,
                front TEXT NOT NULL,
                back TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created flashcard_cards table")

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

        # Create nodes table (for roadmap structure)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                roadmap_id UUID NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
                parent_id UUID REFERENCES nodes(id) ON DELETE CASCADE,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                type VARCHAR(50),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
            );
        """)
        logger.info("Created nodes table")

        # Create progress table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                user_id UUID NOT NULL,
                lesson_id VARCHAR(100) NOT NULL,
                status VARCHAR(50) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, lesson_id)
            );
        """)
        logger.info("Created progress table")

        # Create video_progress table
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS video_progress (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                video_uuid UUID NOT NULL REFERENCES videos(uuid) ON DELETE CASCADE,
                user_id UUID NOT NULL,
                completion_percentage FLOAT DEFAULT 0,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(video_uuid, user_id)
            );
        """)
        logger.info("Created video_progress table")

        # Create indexes for performance
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_flashcard_decks_user_id ON flashcard_decks(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_books_user_id ON books(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_roadmaps_user_id ON roadmaps(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_book_progress_user_id ON book_progress(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_progress_user_id ON progress(user_id);")
        await conn.execute("CREATE INDEX IF NOT EXISTS idx_video_progress_user_id ON video_progress(user_id);")
        logger.info("Created indexes")

        logger.info("All tables created successfully!")

    except Exception as e:
        logger.exception(f"Error creating tables: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(create_tables())
