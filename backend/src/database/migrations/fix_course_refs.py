"""Migration script to fix course ID references in lessons table.

This migration addresses the issue where the lessons table uses course_id
to store node IDs (temporary workaround) by:
1. Adding a proper node_id column to lessons table
2. Migrating existing data from course_id to node_id
3. Updating course_id to reference actual courses (roadmaps)
4. Adding proper foreign key constraints
"""

import asyncio
import logging
from typing import Any

from sqlalchemy import text

from src.database.engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_table_exists(conn: Any, table_name: str) -> bool:
    """Check if a table exists in the database."""
    result = await conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = :table_name
            )
        """),
        {"table_name": table_name},
    )
    return result.scalar()


async def check_column_exists(conn: Any, table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    result = await conn.execute(
        text("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = :table_name
                AND column_name = :column_name
            )
        """),
        {"table_name": table_name, "column_name": column_name},
    )
    return result.scalar()


async def get_lesson_data_backup(conn: Any) -> list[dict[str, Any]]:
    """Create a backup of current lesson data for rollback purposes."""
    try:
        result = await conn.execute(text("SELECT * FROM lesson"))
        lessons = [
            {
                "id": row.id,
                "course_id": row.course_id,
                "slug": row.slug,
                "md_source": row.md_source,
                "html_cache": row.html_cache,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            for row in result
        ]
        logger.info(f"Backed up {len(lessons)} lesson records")
        return lessons
    except Exception:
        logger.exception("Failed to backup lesson data")
        raise


async def fix_course_references() -> None:
    """Fix course ID references in lessons table."""
    async with engine.begin() as conn:
        logger.info("Starting course references migration...")

        # Step 1: Check if lesson table exists
        if not await check_table_exists(conn, "lesson"):
            logger.info("Lesson table doesn't exist, creating it...")
            await conn.execute(
                text("""
                CREATE TABLE lesson (
                    id UUID PRIMARY KEY,
                    course_id UUID NOT NULL,
                    slug TEXT UNIQUE,
                    md_source TEXT NOT NULL,
                    html_cache TEXT,
                    created_at TIMESTAMPTZ DEFAULT now(),
                    updated_at TIMESTAMPTZ DEFAULT now()
                )
                """)
            )
            logger.info("Lesson table created")
            return  # No migration needed for new table

        # Step 2: Create backup of existing data
        await get_lesson_data_backup(conn)

        # Step 3: Check if node_id column already exists
        if await check_column_exists(conn, "lesson", "node_id"):
            logger.info("node_id column already exists in lesson table")
            return

        try:
            # Step 4: Add node_id column
            logger.info("Adding node_id column to lesson table...")
            await conn.execute(
                text("""
                ALTER TABLE lesson
                ADD COLUMN node_id UUID
                """)
            )
            logger.info("node_id column added successfully")

            # Step 5: Migrate existing data - move current course_id values to node_id
            logger.info("Migrating existing course_id values to node_id...")
            await conn.execute(
                text("""
                UPDATE lesson
                SET node_id = course_id
                WHERE node_id IS NULL
                """)
            )
            logger.info("Existing course_id values migrated to node_id")

            # Step 6: Update course_id to reference actual roadmaps
            logger.info("Updating course_id to reference actual roadmaps...")

            # Find the roadmap_id for each node and update the lesson's course_id
            updated_count = await conn.execute(
                text("""
                UPDATE lesson
                SET course_id = n.roadmap_id
                FROM nodes n
                WHERE lesson.node_id = n.id
                """)
            )
            logger.info(f"Updated course_id for lessons: {updated_count.rowcount} rows affected")

            # Step 7: Handle lessons with nodes that don't exist (orphaned lessons)
            orphaned_result = await conn.execute(
                text("""
                SELECT COUNT(*) as count
                FROM lesson l
                LEFT JOIN nodes n ON l.node_id = n.id
                WHERE n.id IS NULL
                """)
            )
            orphaned_count = orphaned_result.scalar()

            if orphaned_count > 0:
                logger.warning(f"Found {orphaned_count} orphaned lessons (node_id doesn't exist in nodes table)")
                logger.info("Setting course_id to NULL for orphaned lessons...")
                await conn.execute(
                    text("""
                    UPDATE lesson
                    SET course_id = NULL
                    FROM (
                        SELECT l.id
                        FROM lesson l
                        LEFT JOIN nodes n ON l.node_id = n.id
                        WHERE n.id IS NULL
                    ) orphaned
                    WHERE lesson.id = orphaned.id
                    """)
                )

            # Step 8: Make node_id NOT NULL after migration
            logger.info("Making node_id column NOT NULL...")
            await conn.execute(
                text("""
                ALTER TABLE lesson
                ALTER COLUMN node_id SET NOT NULL
                """)
            )

            # Step 9: Add foreign key constraints
            logger.info("Adding foreign key constraints...")

            # Add foreign key for node_id
            await conn.execute(
                text("""
                ALTER TABLE lesson
                ADD CONSTRAINT fk_lesson_node_id
                FOREIGN KEY (node_id) REFERENCES nodes(id) ON DELETE CASCADE
                """)
            )

            # Add foreign key for course_id (allow NULL for orphaned lessons)
            await conn.execute(
                text("""
                ALTER TABLE lesson
                ADD CONSTRAINT fk_lesson_course_id
                FOREIGN KEY (course_id) REFERENCES roadmaps(id) ON DELETE CASCADE
                """)
            )

            # Step 10: Create indexes for better performance
            logger.info("Creating indexes...")
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lesson_node_id ON lesson(node_id)"))
            await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_lesson_course_id ON lesson(course_id)"))

            logger.info("Course references migration completed successfully!")

        except Exception as e:
            logger.exception(f"Migration failed: {e}")
            logger.info("Rolling back changes...")
            raise


async def rollback_migration() -> None:
    """Rollback the course references migration."""
    async with engine.begin() as conn:
        logger.info("Starting rollback of course references migration...")

        try:
            # Drop foreign key constraints
            logger.info("Dropping foreign key constraints...")
            await conn.execute(text("ALTER TABLE lesson DROP CONSTRAINT IF EXISTS fk_lesson_node_id"))
            await conn.execute(text("ALTER TABLE lesson DROP CONSTRAINT IF EXISTS fk_lesson_course_id"))

            # Drop indexes
            logger.info("Dropping indexes...")
            await conn.execute(text("DROP INDEX IF EXISTS idx_lesson_node_id"))
            await conn.execute(text("DROP INDEX IF EXISTS idx_lesson_course_id"))

            # Remove node_id column
            logger.info("Removing node_id column...")
            await conn.execute(text("ALTER TABLE lesson DROP COLUMN IF EXISTS node_id"))

            logger.info("Rollback completed successfully!")

        except Exception as e:
            logger.exception(f"Rollback failed: {e}")
            raise


async def validate_migration() -> None:
    """Validate that the migration was successful."""
    async with engine.begin() as conn:
        logger.info("Validating migration...")

        # Check that node_id column exists and is not null
        node_id_check = await conn.execute(
            text("""
                SELECT COUNT(*) as count
                FROM lesson
                WHERE node_id IS NULL
            """)
        )
        null_count = node_id_check.scalar()
        if null_count > 0:
            msg = f"Migration validation failed: {null_count} lessons have NULL node_id"
            raise ValueError(msg)

        # Check that all node_ids reference existing nodes
        orphaned_check = await conn.execute(
            text("""
                SELECT COUNT(*) as count
                FROM lesson l
                LEFT JOIN nodes n ON l.node_id = n.id
                WHERE n.id IS NULL
            """)
        )
        orphaned_count = orphaned_check.scalar()
        if orphaned_count > 0:
            logger.warning(f"Found {orphaned_count} lessons with node_ids that don't exist in nodes table")

        # Check that course_ids reference existing roadmaps (when not NULL)
        invalid_course_check = await conn.execute(
            text("""
                SELECT COUNT(*) as count
                FROM lesson l
                LEFT JOIN roadmaps r ON l.course_id = r.id
                WHERE l.course_id IS NOT NULL AND r.id IS NULL
            """)
        )
        invalid_course_count = invalid_course_check.scalar()
        if invalid_course_count > 0:
            msg = f"Migration validation failed: {invalid_course_count} lessons have invalid course_id"
            raise ValueError(msg)

        # Get migration statistics
        stats = await conn.execute(
            text("""
                SELECT
                    COUNT(*) as total_lessons,
                    COUNT(CASE WHEN course_id IS NOT NULL THEN 1 END) as lessons_with_course,
                    COUNT(CASE WHEN course_id IS NULL THEN 1 END) as orphaned_lessons
                FROM lesson
            """)
        )

        row = stats.first()
        logger.info("Migration validation successful!")
        logger.info(f"Total lessons: {row.total_lessons}")
        logger.info(f"Lessons with valid course reference: {row.lessons_with_course}")
        logger.info(f"Orphaned lessons: {row.orphaned_lessons}")


async def main() -> None:
    """Run the migration."""
    try:
        await fix_course_references()
        await validate_migration()
        logger.info("Course references migration completed successfully!")
    except Exception:
        logger.exception("Course references migration failed")
        logger.info("To rollback, run: python -m src.database.migrations.fix_course_refs rollback")
        raise


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "rollback":
        asyncio.run(rollback_migration())
    else:
        asyncio.run(main())
