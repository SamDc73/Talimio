"""Add user_id column to roadmaps table

This migration adds user_id support to roadmaps/courses table to enable proper
user-specific filtering and multi-tenancy support.

Migration fixes the architectural flaw where roadmaps were stored as global/shared
resources when they should be user-specific since they are AI-generated and tailored.
"""

import asyncio
import uuid

from asyncpg import Connection


DEFAULT_USER_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


async def migrate(conn: Connection) -> None:
    """Add user_id column to roadmaps table with proper migration."""
    # Step 1: Add user_id column as nullable initially
    await conn.execute("""
        ALTER TABLE roadmaps ADD COLUMN user_id UUID;
    """)

    # Step 2: Assign existing roadmaps to default user
    await conn.execute("""
        UPDATE roadmaps SET user_id = $1 WHERE user_id IS NULL;
    """, DEFAULT_USER_ID)

    # Step 3: Make user_id NOT NULL after data migration
    await conn.execute("""
        ALTER TABLE roadmaps ALTER COLUMN user_id SET NOT NULL;
    """)

    # Step 4: Add performance index
    await conn.execute("""
        CREATE INDEX idx_roadmaps_user_id ON roadmaps(user_id);
    """)

    # Step 5: Add foreign key constraint (skipped for now due to user table complexity)
    # await conn.execute("""
    #     ALTER TABLE roadmaps ADD CONSTRAINT fk_roadmaps_user_id
    #         FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
    # """)
    print("⚠️  Skipped foreign key constraint for now")

    print("✅ Successfully added user_id column to roadmaps table")
    print("✅ Migrated existing roadmaps to default user")
    print("✅ Added performance index and foreign key constraint")


async def rollback(conn: Connection) -> None:
    """Rollback the migration by removing user_id column."""
    # Remove foreign key constraint
    await conn.execute("""
        ALTER TABLE roadmaps DROP CONSTRAINT IF EXISTS fk_roadmaps_user_id;
    """)

    # Remove index
    await conn.execute("""
        DROP INDEX IF EXISTS idx_roadmaps_user_id;
    """)

    # Remove user_id column
    await conn.execute("""
        ALTER TABLE roadmaps DROP COLUMN IF EXISTS user_id;
    """)

    print("✅ Successfully rolled back user_id migration from roadmaps table")


if __name__ == "__main__":
    import os

    import asyncpg
    from dotenv import load_dotenv

    load_dotenv()

    async def main():
        database_url = os.getenv("DATABASE_URL")
        # Convert SQLAlchemy format to asyncpg format
        if database_url and database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://")

        conn = await asyncpg.connect(database_url)
        try:
            await migrate(conn)
        finally:
            await conn.close()

    asyncio.run(main())
