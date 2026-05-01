import uuid

from sqlalchemy.ext.asyncio import AsyncSession


"""Business logic for progress tracking."""


import json
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Protocol

from pydantic import JsonValue
from sqlalchemy import text

from src.exceptions import NotFoundError

from .models import ContentType, ProgressResponse, ProgressUpdate
from .queries import (
    DELETE_PROGRESS_QUERY,
    GET_SINGLE_PROGRESS_QUERY,
    UPSERT_PROGRESS_QUERY,
)


logger = logging.getLogger(__name__)


class ProgressRow(Protocol):
    """Database row fields needed to build progress responses."""

    id: uuid.UUID
    content_id: uuid.UUID
    content_type: ContentType
    progress_percentage: float
    metadata: object
    created_at: datetime
    updated_at: datetime


def _json_value_from_unknown(value: object) -> tuple[bool, JsonValue]:
    """Return JSON-compatible values while dropping arbitrary Python objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return True, value
    if isinstance(value, Mapping):
        normalized: dict[str, JsonValue] = {}
        for key, item in value.items():
            valid, json_value = _json_value_from_unknown(item)
            if isinstance(key, str) and valid:
                normalized[key] = json_value
        return True, normalized
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        normalized: list[JsonValue] = []
        for item in value:
            valid, json_value = _json_value_from_unknown(item)
            if valid:
                normalized.append(json_value)
        return True, normalized
    return False, None


def _json_object_from_unknown(value: object) -> dict[str, JsonValue]:
    """Normalize raw JSON metadata into a JSON object."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, JsonValue] = {}
    for key, item in value.items():
        valid, json_value = _json_value_from_unknown(item)
        if isinstance(key, str) and valid:
            normalized[key] = json_value
    return normalized


def _progress_percentage_from_unknown(value: object) -> float:
    """Normalize dynamic course progress percentages."""
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


class ProgressService:
    """Service for managing progress across all content types."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize progress service."""
        self.session = session

    async def get_single_progress(self, user_id: uuid.UUID, content_id: uuid.UUID) -> ProgressResponse | None:
        """Get progress for a single content item."""
        result = await self.session.execute(
            text(GET_SINGLE_PROGRESS_QUERY), {"user_id": str(user_id), "content_id": str(content_id)}
        )

        row = result.first()
        if not row:
            return None

        return self._row_to_progress_response(row)

    async def get_progress_response(self, user_id: uuid.UUID, content_id: uuid.UUID) -> ProgressResponse:
        """Get progress with canonical course progress where applicable."""
        from src.courses.services.course_progress_service import CourseProgressService

        content_type = await self.require_content_type(content_id, user_id)

        if content_type == "course":
            row = await self.get_single_progress(user_id, content_id)
            computed = await CourseProgressService(self.session).get_progress(content_id, user_id)
            metadata = _json_object_from_unknown({key: value for key, value in computed.items() if key != "completion_percentage"})
            return ProgressResponse(
                id=row.id if row else None,
                content_id=content_id,
                content_type="course",
                progress_percentage=_progress_percentage_from_unknown(computed.get("completion_percentage", 0.0)),
                metadata=metadata,
                created_at=row.created_at if row else None,
                updated_at=row.updated_at if row else None,
            )

        progress = await self.get_single_progress(user_id, content_id)
        if progress is not None:
            return progress

        return ProgressResponse(
            id=None,
            content_id=content_id,
            content_type=content_type,
            progress_percentage=0.0,
            metadata={},
            created_at=None,
            updated_at=None,
        )

    async def update_progress(
        self,
        user_id: uuid.UUID,
        content_id: uuid.UUID,
        content_type: ContentType,
        progress: ProgressUpdate,
    ) -> ProgressResponse:
        """Update or create progress for a content item."""
        # Convert metadata to JSON string for PostgreSQL JSONB field
        metadata_json = json.dumps(progress.metadata) if progress.metadata else json.dumps({})

        logger.info(
            "Updating progress for content %s: %s%% with metadata: %s",
            content_id,
            progress.progress_percentage,
            progress.metadata,
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
        if row is None:
            msg = "Progress upsert did not return a row"
            raise RuntimeError(msg)

        await self.session.flush()
        return self._row_to_progress_response(row)

    async def delete_progress(self, user_id: uuid.UUID, content_id: uuid.UUID) -> None:
        """Delete progress for a content item."""
        result = await self.session.execute(
            text(DELETE_PROGRESS_QUERY), {"user_id": str(user_id), "content_id": str(content_id)}
        )

        affected = getattr(result, "rowcount", 0)
        await self.session.flush()
        if not affected or affected <= 0:
            raise NotFoundError(message=f"Progress for content {content_id} not found", feature_area="progress")

    @staticmethod
    def _row_to_progress_response(row: ProgressRow) -> ProgressResponse:
        """Convert a database row into a ProgressResponse."""
        return ProgressResponse(
            id=row.id,
            content_id=row.content_id,
            content_type=row.content_type,
            progress_percentage=row.progress_percentage,
            metadata=_json_object_from_unknown(row.metadata),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_content_type(self, content_id: uuid.UUID, user_id: uuid.UUID) -> ContentType | None:
        """Determine content type by checking which table contains the content AND user owns it."""
        # Check books (uses id column which is uuid.UUID)
        result = await self.session.execute(
            text("SELECT 1 FROM books WHERE id = :content_id AND user_id = :user_id"),
            {"content_id": str(content_id), "user_id": str(user_id)},
        )
        if result.first():
            return "book"

        # Check videos (uses id column which is uuid.UUID)
        result = await self.session.execute(
            text("SELECT 1 FROM videos WHERE id = :content_id AND user_id = :user_id"),
            {"content_id": str(content_id), "user_id": str(user_id)},
        )
        if result.first():
            return "video"

        # Check courses (uses id column which is uuid.UUID)
        result = await self.session.execute(
            text("SELECT 1 FROM courses WHERE id = :content_id AND user_id = :user_id"),
            {"content_id": str(content_id), "user_id": str(user_id)},
        )
        if result.first():
            return "course"

        return None

    async def require_content_type(self, content_id: uuid.UUID, user_id: uuid.UUID) -> ContentType:
        """Return the owned content type or raise a domain not-found error."""
        content_type = await self.get_content_type(content_id, user_id)
        if content_type is None:
            raise NotFoundError(
                message=f"Content {content_id} not found or access denied",
                feature_area="progress",
            )
        return content_type
