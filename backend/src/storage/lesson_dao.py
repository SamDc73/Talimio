from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import asyncpg


class LessonDAO:
    """Data Access Object for lesson-related database operations."""

    @staticmethod
    async def get_connection() -> asyncpg.Connection:
        """Get a database connection from the pool."""
        # Use environment variables for connection
        import logging
        import os

        # Use DATABASE_URL if available, otherwise fallback to individual settings
        connection_string = os.getenv("DATABASE_URL")
        if connection_string:
            # Convert SQLAlchemy-style URL to asyncpg-compatible URL
            if connection_string.startswith("postgresql+asyncpg://"):
                connection_string = connection_string.replace("postgresql+asyncpg://", "postgresql://")
            logging.info("Connecting to database using DATABASE_URL")
        else:
            # Default to localhost if not specified
            host = os.getenv("POSTGRES_HOST", "localhost")
            port = os.getenv("POSTGRES_PORT", "5432")
            user = os.getenv("POSTGRES_USER", "postgres")
            password = os.getenv("POSTGRES_PASSWORD", "postgres")
            dbname = os.getenv("POSTGRES_DB", "postgres")
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
            logging.info(f"Connecting to database at {host}:{port}/{dbname}")

        try:
            return await asyncpg.connect(connection_string)
        except Exception as e:
            logging.exception(f"Failed to connect to database: {e!s}")
            raise

    @staticmethod
    def _record_to_dict(record: asyncpg.Record | None) -> dict[str, Any] | None:
        """Convert an asyncpg record to a dictionary."""
        if record is None:
            return None
        return dict(record)

    @classmethod
    async def insert(cls, lesson_data: dict[str, Any]) -> dict[str, Any] | None:
        """Insert a new lesson into the database or return existing one if it already exists."""
        conn = await cls.get_connection()
        try:
            row = await conn.fetchrow(
                """
                INSERT INTO lesson (
                    id, course_id, slug, md_source, node_id, html_cache,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (id) DO NOTHING
                RETURNING *
                """,
                lesson_data["id"],
                lesson_data["course_id"],
                lesson_data["slug"],
                lesson_data["md_source"],
                lesson_data.get("node_id"),
                lesson_data.get("html_cache"),
                lesson_data["created_at"],
                lesson_data["updated_at"],
            )
            
            # If insert was skipped due to conflict, fetch the existing record
            if row is None:
                row = await conn.fetchrow("SELECT * FROM lesson WHERE id = $1", lesson_data["id"])
            
            return cls._record_to_dict(row)
        finally:
            await conn.close()

    @classmethod
    async def get_by_id(cls, lesson_id: UUID) -> dict[str, Any] | None:
        """Retrieve a lesson by its ID."""
        conn = await cls.get_connection()
        try:
            row = await conn.fetchrow("SELECT * FROM lesson WHERE id = $1", lesson_id)
            return cls._record_to_dict(row)
        finally:
            await conn.close()

    @classmethod
    async def get_by_node(cls, node_id: str) -> list[dict[str, Any]]:
        """Retrieve all lessons for a given node.

        In the current implementation, we use the course_id field to store the node_id.
        This is a temporary solution until we update the database schema.
        """
        conn = await cls.get_connection()
        try:
            rows = await conn.fetch("SELECT * FROM lesson WHERE course_id = $1 ORDER BY created_at DESC", node_id)
            return [cast("dict[str, Any]", cls._record_to_dict(row)) for row in rows if row is not None]
        finally:
            await conn.close()

    @classmethod
    async def update(cls, lesson_id: UUID, data: dict[str, Any]) -> dict[str, Any] | None:
        """Update a lesson by its ID."""
        conn = await cls.get_connection()
        try:
            set_clauses = []
            params: list[Any] = [lesson_id]
            param_counter = 2

            for key in data:
                if key not in ["id", "created_at"]:  # Protect certain fields
                    set_clauses.append(f"{key} = ${param_counter}")
                    params.append(data[key])
                    param_counter += 1

            if not set_clauses:
                return None

            # Always update the updated_at timestamp
            set_clauses.append("updated_at = $" + str(param_counter))
            params.append(datetime.now(UTC))

            query = f"""
                UPDATE lesson
                SET {", ".join(set_clauses)}
                WHERE id = $1
                RETURNING *
            """
            row = await conn.fetchrow(query, *params)
            return cls._record_to_dict(row)
        finally:
            await conn.close()

    @classmethod
    async def delete(cls, lesson_id: UUID) -> bool:
        """Delete a lesson by its ID."""
        conn = await cls.get_connection()
        try:
            result = await conn.execute("DELETE FROM lesson WHERE id = $1", lesson_id)
            return "DELETE 1" in result
        finally:
            await conn.close()

    @classmethod
    async def list_lessons(cls, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        """List lessons with pagination."""
        conn = await cls.get_connection()
        try:
            rows = await conn.fetch(
                """
                SELECT * FROM lesson
                ORDER BY created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )
            return [cast("dict[str, Any]", cls._record_to_dict(row)) for row in rows if row is not None]
        finally:
            await conn.close()
