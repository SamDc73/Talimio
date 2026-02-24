"""Main content service."""

import logging
from typing import TYPE_CHECKING, Any

from fastapi.concurrency import run_in_threadpool
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError

from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService
from src.exceptions import ResourceNotFoundError


if TYPE_CHECKING:
    import uuid

    from sqlalchemy.ext.asyncio import AsyncSession


# Progress calculation imports removed - progress now fetched separately
# AuthContext removed - using uuid.UUID directly
logger = logging.getLogger(__name__)


class ContentService:
    """Main service for content operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the content service."""
        self._session = session

    async def list_content_fast(
        self,
        user_id: uuid.UUID,
        search: str | None = None,
        content_type: ContentType | None = None,
        page: int = 1,
        page_size: int = 20,
        include_archived: bool = False,
    ) -> ContentListResponse:
        """
        Ultra-fast content listing using raw SQL queries.

        This version:
        1. Uses raw SQL for maximum performance
        2. Fetches only essential fields
        3. Single database round-trip
        4. No ORM overhead
        """
        offset = (page - 1) * page_size
        search_term = f"%{search}%" if search else None

        session = self._session
        queries = QueryBuilderService.build_content_queries(content_type, search, include_archived, user_id)

        if not queries:
            return ContentListResponse(items=[], total=0, page=page, per_page=page_size)

        combined_query = " UNION ALL ".join(f"({q})" for q in queries)
        total = await QueryBuilderService.get_total_count(session, combined_query, search_term, user_id)
        rows = await self.get_paginated_results(session, combined_query, search_term, page_size, offset, user_id)
        items = ContentTransformService.transform_rows_to_items(rows)

        # PERFORMANCE OPTIMIZATION: Progress calculations removed
        # Progress is now fetched separately via /api/v1/progress endpoints
        # This reduces content endpoint response time from 300ms+ to <100ms

        # Log archive status of returned items
        archived_count = sum(1 for item in items if hasattr(item, "archived") and item.archived)
        active_count = len(items) - archived_count
        logger.info(
            "📊 Returning %s items: %s archived, %s active",
            len(items),
            archived_count,
            active_count,
        )

        for item in items:
            if hasattr(item, "archived"):
                logger.info(
                    "🔍 Item '%s': archived=%s, type=%s",
                    item.title,
                    item.archived,
                    item.__class__.__name__,
                )

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            per_page=page_size,
        )

    async def get_paginated_results(
        self,
        session: AsyncSession,
        combined_query: str,
        search_term: str | None,
        page_size: int,
        offset: int,
        user_id: uuid.UUID | None = None,
    ) -> list[Any]:
        """Get paginated results."""
        combined_subquery = QueryBuilderService.build_combined_subquery(combined_query)
        statement = (
            select(combined_subquery)
            .order_by(combined_subquery.c.last_accessed.desc())
            .limit(page_size)
            .offset(offset)
        )
        params: dict[str, Any] = {}
        if search_term:
            params["search"] = search_term
        # Only include user_id if it's not None (since we build different queries based on user_id)
        if user_id is not None:
            params["user_id"] = user_id
            logger.info("Executing query with user_id: %s", user_id)
        else:
            logger.info("Executing query without user_id")

        result = await session.execute(statement, params)
        return list(result.all())

    async def _delete_book_file(self, row: Any) -> None:
        """Best-effort deletion of stored file for books."""
        if getattr(row, "file_path", None):
            try:
                from src.storage.factory import get_storage_provider

                storage = get_storage_provider()
                await storage.delete(row.file_path)
            except (OSError, RuntimeError, TypeError, ValueError):
                logger.exception("Non-fatal: failed to delete stored file for book")

    async def _delete_course_document_files(self, session: AsyncSession, course_id: uuid.UUID) -> None:
        """Delete any local source files for course documents.

        Course reference docs (used for course RAG) are stored on the local filesystem
        during upload/processing. We remove any lingering files here to guarantee
        no leftovers after a hard delete.
        """
        try:
            result = await session.execute(
                text(
                    """
                    SELECT id, file_path FROM course_documents
                    WHERE course_id = :course_id AND file_path IS NOT NULL
                    """
                ),
                {"course_id": str(course_id)},
            )
            rows = result.fetchall()
            for row in rows:
                file_path = getattr(row, "file_path", None)
                if not file_path:
                    continue
                # Best-effort local unlink; ignore failures
                try:
                    from pathlib import Path

                    p = Path(file_path)
                    if await run_in_threadpool(p.exists):
                        await run_in_threadpool(p.unlink)
                except OSError:
                    logger.debug("Non-fatal: failed to delete course doc file %s", file_path)
        except SQLAlchemyError:
            # Don't block overall deletion if this best-effort cleanup fails
            logger.debug("Course document file cleanup failed for course %s", course_id)

    async def _prune_orphan_tags(self, session: AsyncSession) -> None:
        """Remove Tag rows that are no longer referenced by any content.

        Keeps the tag table tidy after hard deletes. Safe since tags are global and
        only valuable when associated.
        """
        try:
            await session.execute(
                text("DELETE FROM tags t WHERE NOT EXISTS (SELECT 1 FROM tag_associations ta WHERE ta.tag_id = t.id)")
            )
        except SQLAlchemyError:
            logger.debug("Non-fatal: failed to prune orphan tags", exc_info=True)

    def _get_model(self, content_type: ContentType) -> Any:
        """Map content type to ORM model."""
        from src.books.models import Book
        from src.courses.models import Course
        from src.videos.models import Video

        mapping: dict[ContentType, Any] = {
            ContentType.BOOK: Book,
            ContentType.VIDEO: Video,
            ContentType.COURSE: Course,
        }
        return mapping[content_type]

    async def _delete_progress_for_content(self, session: AsyncSession, row_id: uuid.UUID) -> None:
        """Delete all progress rows for a content item; tolerate absence."""
        try:
            await session.execute(
                text("DELETE FROM user_progress WHERE content_id = :content_id"),
                {"content_id": str(row_id)},
            )
        except SQLAlchemyError:
            logger.debug("Non-fatal: failed to delete user progress for content %s", row_id, exc_info=True)

    async def _delete_highlights(
        self,
        session: AsyncSession,
        content_type: ContentType,
        row_id: uuid.UUID,
    ) -> None:
        """Delete highlights for this content regardless of user_id."""
        from sqlalchemy import and_, delete

        from src.highlights.models import Highlight

        try:
            await session.execute(
                delete(Highlight).where(
                    and_(
                        Highlight.content_id == row_id,
                        Highlight.content_type == content_type.value,
                    )
                )
            )
        except SQLAlchemyError:
            logger.debug("Non-fatal: failed to delete highlights for content %s", row_id, exc_info=True)

    async def _delete_tag_associations(
        self,
        session: AsyncSession,
        content_type: ContentType,
        row_id: uuid.UUID,
    ) -> None:
        """Delete tag associations for this content regardless of user_id."""
        from sqlalchemy import and_, delete

        from src.tagging.models import TagAssociation

        await session.execute(
            delete(TagAssociation).where(
                and_(
                    TagAssociation.content_id == row_id,
                    TagAssociation.content_type == content_type.value,
                )
            )
        )

    async def delete_content(
        self,
        content_type: ContentType,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a content item and all related references."""
        session = self._session
        model = self._get_model(content_type)

        # Load row with ownership check
        row = await session.get(model, content_id)
        if row is None or getattr(row, "user_id", None) != user_id:
            raise ResourceNotFoundError(content_type.value, str(content_id))

        # Remove any stored files that rely on row attributes before deleting the row.
        if content_type == ContentType.BOOK:
            await self._delete_book_file(row)
        elif content_type == ContentType.COURSE:
            # Also remove any lingering uploaded course document source files
            await self._delete_course_document_files(session, content_id)

        # Cross-module cleanup
        await self._delete_progress_for_content(session, content_id)
        await self._delete_highlights(session, content_type, content_id)
        await self._delete_tag_associations(session, content_type, content_id)
        await self._prune_orphan_tags(session)

        from src.ai.rag.service import RAGService

        await RAGService.purge_for_content(session, content_type.value, content_id)

        # Delete the content row and let the request boundary commit.
        await session.delete(row)
        await session.flush()
