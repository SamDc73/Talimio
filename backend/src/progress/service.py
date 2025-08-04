"""Business logic for progress tracking."""

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import ContentType, ProgressResponse, ProgressUpdate
from .queries import (
    DELETE_PROGRESS_QUERY,
    GET_BATCH_PROGRESS_QUERY,
    GET_SINGLE_PROGRESS_QUERY,
    UPSERT_PROGRESS_QUERY,
)


logger = logging.getLogger(__name__)


class ProgressService:
    """Service for managing progress across all content types."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize progress service."""
        self.session = session

    async def get_batch_progress(self, user_id: UUID, content_ids: list[UUID]) -> dict[str, dict[str, Any]]:
        """Get progress for multiple content items."""
        if not content_ids:
            return {}

        result = await self.session.execute(
            text(GET_BATCH_PROGRESS_QUERY), {"user_id": str(user_id), "content_ids": [str(cid) for cid in content_ids]}
        )

        progress_map = {}
        for row in result:
            # Parse metadata if it's a string (JSON)
            metadata = row.metadata
            if isinstance(metadata, str):
                try:
                    metadata = json.loads(metadata)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata for content {row.content_id}: {metadata}")
                    metadata = {}
            elif metadata is None:
                metadata = {}

            progress_map[str(row.content_id)] = {"progress_percentage": row.progress_percentage, "metadata": metadata}

        return progress_map

    async def get_single_progress(self, user_id: UUID, content_id: UUID) -> ProgressResponse | None:
        """Get progress for a single content item."""
        result = await self.session.execute(
            text(GET_SINGLE_PROGRESS_QUERY), {"user_id": str(user_id), "content_id": str(content_id)}
        )

        row = result.first()
        if not row:
            return None

        return ProgressResponse(
            id=row.id,
            user_id=row.user_id,
            content_id=row.content_id,
            content_type=row.content_type,
            progress_percentage=row.progress_percentage,
            metadata=row.metadata or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def update_progress(
        self,
        user_id: UUID,
        content_id: UUID,
        content_type: ContentType,
        progress: ProgressUpdate,
    ) -> ProgressResponse:
        """Update or create progress for a content item."""
        # Convert metadata to JSON string for PostgreSQL JSONB field
        metadata_json = json.dumps(progress.metadata) if progress.metadata else json.dumps({})

        logger.info(
            f"Updating progress for content {content_id}: {progress.progress_percentage}% with metadata: {progress.metadata}"
        )

        result = await self.session.execute(
            text(UPSERT_PROGRESS_QUERY),
            {
                "user_id": str(user_id),
                "content_id": str(content_id),
                "content_type": content_type,
                "progress_percentage": progress.progress_percentage,
                "metadata": metadata_json,
            },
        )

        row = result.first()
        await self.session.commit()

        return ProgressResponse(
            id=row.id,
            user_id=row.user_id,
            content_id=row.content_id,
            content_type=row.content_type,
            progress_percentage=row.progress_percentage,
            metadata=row.metadata or {},
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def delete_progress(self, user_id: UUID, content_id: UUID) -> bool:
        """Delete progress for a content item."""
        result = await self.session.execute(
            text(DELETE_PROGRESS_QUERY), {"user_id": str(user_id), "content_id": str(content_id)}
        )

        await self.session.commit()
        return result.rowcount > 0

    async def get_content_type(self, content_id: UUID) -> ContentType | None:
        """Determine content type by checking which table contains the content."""
        # Check books (uses id column which is UUID)
        result = await self.session.execute(
            text("SELECT 1 FROM books WHERE id = :content_id"), {"content_id": str(content_id)}
        )
        if result.first():
            return "book"

        # Check videos (uses id column which is UUID)
        result = await self.session.execute(
            text("SELECT 1 FROM videos WHERE id = :content_id"), {"content_id": str(content_id)}
        )
        if result.first():
            return "video"

        # Check courses/roadmaps (uses id column which is UUID)
        result = await self.session.execute(
            text("SELECT 1 FROM roadmaps WHERE id = :content_id"), {"content_id": str(content_id)}
        )
        if result.first():
            return "course"

        return None
