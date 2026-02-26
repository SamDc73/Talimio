"""Content archive service."""

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentListResponse, ContentType, normalize_content_type
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService
from src.exceptions import ResourceNotFoundError


logger = logging.getLogger(__name__)


class ContentArchiveService:
    """Service for archiving and unarchiving content."""

    @staticmethod
    async def archive_content(db: AsyncSession, content_type: ContentType, content_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Archive content by type and ID with user validation."""
        logger.info("🗃️ Archiving %s %s", content_type, content_id)

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
            logger.error(msg)
            raise ValueError(msg)

        logger.info("🔍 With params: content_id=%s, user_id=%s", content_id, user_id)
        result = await db.execute(statement, params)
        affected_rows = int(getattr(result, "rowcount", 0) or 0)
        await db.flush()

        logger.info("📊 Archive operation affected %s rows", affected_rows)

        if affected_rows == 0:
            logger.warning("⚠️ Content %s not found or access denied", content_id)
            raise ResourceNotFoundError(content_type.value, str(content_id))
        logger.info("✅ Successfully archived %s", content_id)

    @staticmethod
    async def unarchive_content(db: AsyncSession, content_type: ContentType, content_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Unarchive content by type and ID with user validation."""
        logger.info("📤 Unarchiving %s %s", content_type, content_id)

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
            logger.error(msg)
            raise ValueError(msg)

        logger.info("🔍 With params: content_id=%s, user_id=%s", content_id, user_id)
        result = await db.execute(statement, params)
        affected_rows = int(getattr(result, "rowcount", 0) or 0)
        await db.flush()

        logger.info("📊 Unarchive operation affected %s rows", affected_rows)

        if affected_rows == 0:
            logger.warning("⚠️ Content %s not found or access denied", content_id)
            raise ResourceNotFoundError(content_type.value, str(content_id))
        logger.info("✅ Successfully unarchived %s", content_id)

    @staticmethod
    async def list_archived_content(
        session: AsyncSession,
        search: str | None = None,
        content_type: ContentType | None = None,
        page: int = 1,
        page_size: int = 20,
        current_user_id: uuid.UUID | None = None,
    ) -> ContentListResponse:
        """
        List only archived content across different types.

        Similar to list_content_fast but filters for archived = true.
        """
        from src.content.services.content_service import ContentService

        offset = (page - 1) * page_size
        search_term = f"%{search}%" if search else None

        # Construct the combined query with archived filter
        if content_type:
            canonical_content_type = normalize_content_type(content_type)

            if canonical_content_type == ContentType.VIDEO:
                combined_query = QueryBuilderService.get_video_query(
                    search,
                    archived_only=True,
                    user_id=current_user_id,
                )
            elif canonical_content_type == ContentType.BOOK:
                combined_query = QueryBuilderService.get_books_query(
                    search, archived_only=True, user_id=current_user_id
                )
            elif canonical_content_type == ContentType.COURSE:
                combined_query = QueryBuilderService.get_courses_query(
                    search, archived_only=True, include_archived=False, user_id=current_user_id
                )
            else:
                msg = f"Unsupported content type: {content_type}"
                raise ValueError(msg)
        else:
            # Union all content types with archived filter
            combined_query = f"""
                {QueryBuilderService.get_video_query(search, archived_only=True, user_id=current_user_id)}
                UNION ALL
                {QueryBuilderService.get_books_query(search, archived_only=True, user_id=current_user_id)}
                UNION ALL
                {QueryBuilderService.get_courses_query(search, archived_only=True, include_archived=False, user_id=current_user_id)}
            """

        # Get total count and paginated results
        total = await QueryBuilderService.get_total_count(session, combined_query, search_term, current_user_id)
        service = ContentService(session)
        rows = await service.get_paginated_results(
            session, combined_query, search_term, page_size, offset, current_user_id
        )

        # Transform rows to content items
        items = ContentTransformService.transform_rows_to_items(rows)

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            per_page=page_size,
        )
