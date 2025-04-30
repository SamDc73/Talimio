"""
Script to initialize the lesson table in the database.

Run this script manually if the table doesn't exist.
"""

import asyncio
import logging

from src.storage.lesson_dao import LessonDAO


async def create_lesson_table() -> None:
    """Create the lesson table if it doesn't exist."""
    conn = await LessonDAO.get_connection()
    try:
        # Check if table exists
        table_exists = await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'lesson'
            )
            """
        )

        if not table_exists:
            logging.info("Creating lesson table...")
            await conn.execute(
                """
                CREATE TABLE lesson (
                    id UUID PRIMARY KEY,
                    course_id UUID NOT NULL,
                    slug TEXT UNIQUE,
                    md_source TEXT NOT NULL,
                    html_cache TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """
            )
            logging.info("Lesson table created successfully.")
        else:
            logging.info("Lesson table already exists.")
    finally:
        await conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(create_lesson_table())
