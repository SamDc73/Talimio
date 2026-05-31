"""Content archive service."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentType, normalize_content_type
from src.exceptions import NotFoundError


logger = logging.getLogger(__name__)


class ContentArchiveService:
    """Service for archiving and unarchiving content."""

    @staticmethod
    async def archive_content(db: AsyncSession, content_type: ContentType, content_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Archive content by type and ID with user validation."""
        canonical_content_type = normalize_content_type(content_type)

        statement = None
        params: dict[str, uuid.UUID | datetime] = {"content_id": content_id, "user_id": user_id}
        if canonical_content_type == ContentType.BOOK:
            statement = text(
                """
                UPDATE books
                SET archived = true, archived_at = :archived_at
                WHERE id = :content_id AND user_id = :user_id
                """
            )
            params["archived_at"] = datetime.now(UTC)
        elif canonical_content_type == ContentType.VIDEO:
            statement = text(
                """
                UPDATE videos
                SET archived = true, archived_at = :archived_at
                WHERE id = :content_id AND user_id = :user_id
                """
            )
            params["archived_at"] = datetime.now(UTC)
        elif canonical_content_type == ContentType.COURSE:
            statement = text(
                """
                UPDATE courses
                SET archived = true
                WHERE id = :content_id AND user_id = :user_id
                """
            )
        else:
            msg = f"Unsupported content type: {content_type}"
            logger.error("content.archive.unsupported_type", extra={"content_type": str(content_type)})
            raise ValueError(msg)

        result = await db.execute(statement, params)
        affected_rows = int(getattr(result, "rowcount", 0) or 0)
        await db.flush()

        if affected_rows == 0:
            logger.warning("content.archive.not_found", extra={"content_type": content_type.value, "content_id": str(content_id), "user_id": str(user_id)})
            raise NotFoundError(content_type.value, str(content_id))
        logger.info("content.archive.succeeded", extra={"content_type": content_type.value, "content_id": str(content_id), "user_id": str(user_id)})

    @staticmethod
    async def unarchive_content(db: AsyncSession, content_type: ContentType, content_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Unarchive content by type and ID with user validation."""
        canonical_content_type = normalize_content_type(content_type)

        statement = None
        params: dict[str, uuid.UUID] = {"content_id": content_id, "user_id": user_id}
        if canonical_content_type == ContentType.BOOK:
            statement = text(
                """
                UPDATE books
                SET archived = false, archived_at = NULL
                WHERE id = :content_id AND user_id = :user_id
                """
            )
        elif canonical_content_type == ContentType.VIDEO:
            statement = text(
                """
                UPDATE videos
                SET archived = false, archived_at = NULL
                WHERE id = :content_id AND user_id = :user_id
                """
            )
        elif canonical_content_type == ContentType.COURSE:
            statement = text(
                """
                UPDATE courses
                SET archived = false
                WHERE id = :content_id AND user_id = :user_id
                """
            )
        else:
            msg = f"Unsupported content type: {content_type}"
            logger.error("content.unarchive.unsupported_type", extra={"content_type": str(content_type)})
            raise ValueError(msg)

        result = await db.execute(statement, params)
        affected_rows = int(getattr(result, "rowcount", 0) or 0)
        await db.flush()

        if affected_rows == 0:
            logger.warning("content.archive.not_found", extra={"content_type": content_type.value, "content_id": str(content_id), "user_id": str(user_id)})
            raise NotFoundError(content_type.value, str(content_id))
        logger.info("content.unarchive.succeeded", extra={"content_type": content_type.value, "content_id": str(content_id), "user_id": str(user_id)})
