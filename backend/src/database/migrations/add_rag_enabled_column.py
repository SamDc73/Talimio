#!/usr/bin/env python3
"""Migration to add rag_enabled column to roadmaps table.

This migration adds the missing rag_enabled column that the Course model expects.
This fixes the AttributeError when accessing roadmap.rag_enabled in the service layer.
"""

from src.database.engine import get_connection


async def add_rag_enabled_column() -> None:
    """Add rag_enabled column to roadmaps table."""
    connection = await get_connection()

    try:
        # Add the rag_enabled column with default value False
        await connection.execute("""
            ALTER TABLE roadmaps
            ADD COLUMN IF NOT EXISTS rag_enabled BOOLEAN NOT NULL DEFAULT FALSE;
        """)

        # Verify the column was added
        result = await connection.fetch("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'roadmaps' AND column_name = 'rag_enabled';
        """)

        if result:
            result[0]
        else:
            pass

    finally:
        await connection.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(add_rag_enabled_column())
