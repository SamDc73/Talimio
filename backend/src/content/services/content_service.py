"""Main content service."""

import contextlib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentListResponse, ContentType

# Progress calculation imports removed - progress now fetched separately
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService

# AuthContext removed - using UUID directly
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class ContentService:
    """Main service for content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        """Initialize the content service."""
        self._session = session

    async def list_content_fast(
        self,
        user_id: UUID,
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

        # Use provided session or create a new one
        if self._session:
            session = self._session
            queries: list[str] = []

            queries, _needs_user_id = QueryBuilderService.build_content_queries(
                content_type, search, include_archived, user_id
            )

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
            logger.info(f"📊 Returning {len(items)} items: {archived_count} archived, {active_count} active")

            for item in items:
                if hasattr(item, "archived"):
                    logger.info(f"🔍 Item '{item.title}': archived={item.archived}, type={item.__class__.__name__}")

            return ContentListResponse(
                items=items,
                total=total,
                page=page,
                per_page=page_size,
            )
        # Fallback to creating a new session
        async with async_session_maker() as session:
            queries: list[str] = []

            queries, _needs_user_id = QueryBuilderService.build_content_queries(
                content_type, search, include_archived, user_id
            )

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
            logger.info(f"📊 Returning {len(items)} items: {archived_count} archived, {active_count} active")

            for item in items:
                if hasattr(item, "archived"):
                    logger.info(f"🔍 Item '{item.title}': archived={item.archived}, type={item.__class__.__name__}")

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
        user_id: UUID | None = None,
    ) -> list[Any]:
        """Get paginated results."""
        final_query = f"""            SELECT * FROM ({combined_query}) as combined
            ORDER BY last_accessed DESC
            LIMIT :limit OFFSET :offset
        """

        params: dict[str, Any] = {"limit": page_size, "offset": offset}
        if search_term:
            params["search"] = search_term
        # Only include user_id if it's not None (since we build different queries based on user_id)
        if user_id is not None:
            params["user_id"] = user_id
            logger.info(f"Executing query with user_id: {user_id}")
        else:
            logger.info("Executing query without user_id")

        result = await session.execute(text(final_query), params)
        return list(result.all())

    async def _delete_book_file(self, row: Any) -> None:
        """Best-effort deletion of stored file for books."""
        if getattr(row, "file_path", None):
            try:
                from src.storage.factory import get_storage_provider

                storage = get_storage_provider()
                await storage.delete(row.file_path)
            except Exception:
                logger.exception("Non-fatal: failed to delete stored file for book")

    async def _delete_course_document_files(self, session: AsyncSession, course_id: UUID) -> None:
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
                    if p.exists():
                        p.unlink()
                except Exception:
                    logger.debug("Non-fatal: failed to delete course doc file %s", file_path)
        except Exception:
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
        except Exception:
            with contextlib.suppress(Exception):
                await session.rollback()

    def _get_model_and_doc_type(self, content_type: ContentType) -> tuple[Any, str]:
        """Map content type to ORM model and doc_type string."""
        from src.books.models import Book
        from src.courses.models import Course
        from src.videos.models import Video

        mapping: dict[ContentType, tuple[Any, str]] = {
            ContentType.BOOK: (Book, "book"),
            ContentType.YOUTUBE: (Video, "video"),
            ContentType.COURSE: (Course, "course"),
        }
        if content_type not in mapping:
            msg = f"Unsupported content type: {content_type}"
            raise ValueError(msg)
        return mapping[content_type]

    async def _delete_user_progress(self, session: AsyncSession, user_id: UUID, row_id: UUID) -> None:
        """Delete user progress rows; tolerate absence."""
        try:
            await session.execute(
                text("DELETE FROM user_progress WHERE user_id = :user_id AND content_id = :content_id"),
                {"user_id": str(user_id), "content_id": str(row_id)},
            )
        except Exception:
            with contextlib.suppress(Exception):
                await session.rollback()

    async def _delete_tag_associations(
        self,
        session: AsyncSession,
        content_type: ContentType,
        row_id: UUID,
    ) -> None:
        """Delete tag associations for this content regardless of user_id."""
        from sqlalchemy import and_, delete

        from src.tagging.models import TagAssociation

        tag_type = "video" if content_type == ContentType.YOUTUBE else content_type.value
        await session.execute(
            delete(TagAssociation).where(
                and_(
                    TagAssociation.content_id == row_id,
                    TagAssociation.content_type == tag_type,
                )
            )
        )

    async def delete_content(
        self,
        content_type: ContentType,
        content_id: str,
        user_id: UUID,
    ) -> None:
        """Delete a content item and all related references."""
        # Resolve session
        if self._session:
            session = self._session
            own_session = False
        else:
            session = await async_session_maker().__aenter__()
            own_session = True

        try:
            model, _doc_type = self._get_model_and_doc_type(content_type)

            # Parse UUID and load row with ownership check
            obj_id = UUID(content_id)
            row = await session.get(model, obj_id)
            if row is None or getattr(row, "user_id", None) != user_id:
                msg = f"{content_type.value.capitalize()} {content_id} not found"
                raise ValueError(msg)

            # Remove RAG chunks and any stored files
            from src.ai.rag.service import RAGService

            await RAGService.purge_for_content(session, content_type.value, str(obj_id))
            if content_type == ContentType.BOOK:
                await self._delete_book_file(row)
            elif content_type == ContentType.COURSE:
                # Also remove any lingering uploaded course document source files
                await self._delete_course_document_files(session, obj_id)

            # Cross-module cleanup
            await self._delete_user_progress(session, user_id, obj_id)
            await self._delete_tag_associations(session, content_type, obj_id)
            await self._prune_orphan_tags(session)

            # Delete the content row and commit once
            await session.delete(row)
            await session.commit()
        finally:
            if own_session:
                await session.__aexit__(None, None, None)
