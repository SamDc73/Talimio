"""Drop nodes table migration.

This migration removes the nodes table and all related constraints
since we're removing the module functionality from the application.
"""

import asyncpg


async def migrate() -> None:
    """Execute the migration to drop the nodes table."""
    conn = await asyncpg.connect(
        host="localhost",
        port=5432,
        user="postgres",
        password="postgres",  # noqa: S106
        database="learning_roadmap",
    )

    try:
        # Drop the nodes table (this will cascade and remove foreign key references)
        await conn.execute("DROP TABLE IF EXISTS nodes CASCADE;")

        # Also remove the node_id column from lessons table if it exists
        await conn.execute("""
            ALTER TABLE lesson
            DROP COLUMN IF EXISTS node_id;
        """)

    except Exception as e:
        msg = f"Migration failed: {e}"
        raise RuntimeError(msg) from e
    finally:
        await conn.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(migrate())
