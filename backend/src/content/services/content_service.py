"""Main content service."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_progress_service import _calculate_book_progress, _calculate_course_progress
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class ContentService:
    """Main service for content operations."""

    @staticmethod
    async def list_content_fast(
        search: str | None = None,
        content_type: ContentType | None = None,
        page: int = 1,
        page_size: int = 20,
        include_archived: bool = False,
        current_user_id: UUID | None = None,
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
        # For content listing, we don't require authentication
        # If no user is provided, we'll show content with 0% progress
        # current_user_id is already a string or None from the router
        effective_user_id = current_user_id

        async with async_session_maker() as session:
            logger.info(
                f"🔍 list_content_fast called with include_archived={include_archived}, search={search}, content_type={content_type}"
            )

            queries, needs_user_id = QueryBuilderService.build_content_queries(content_type, search, include_archived, effective_user_id)

            if not queries:
                return ContentListResponse(items=[], total=0, page=page, page_size=page_size)

            combined_query = " UNION ALL ".join(f"({q})" for q in queries)
            total = await QueryBuilderService.get_total_count(session, combined_query, search_term, effective_user_id)
            rows = await ContentService.get_paginated_results(session, combined_query, search_term, page_size, offset, effective_user_id)
            items = ContentTransformService.transform_rows_to_items(rows)

            # Calculate accurate progress for courses using CourseProgressService
            if effective_user_id and content_type in (None, "course"):
                items = await _calculate_course_progress(session, items, effective_user_id)

            # Calculate accurate progress for books using BookProgressService
            if effective_user_id and content_type in (None, "book"):
                items = await _calculate_book_progress(session, items, effective_user_id)

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
                page_size=page_size,
            )

    @staticmethod
    async def get_paginated_results(
        session: AsyncSession,
        combined_query: str,
        search_term: str | None,
        page_size: int,
        offset: int,
        user_id: UUID | None = None,
    ) -> list[Any]:
        """Get paginated results."""
        from src.core.user_utils import normalize_user_id

        final_query = f"""
            SELECT * FROM ({combined_query}) as combined
            ORDER BY last_accessed DESC
            LIMIT :limit OFFSET :offset
        """

        params: dict[str, Any] = {"limit": page_size, "offset": offset}
        if search_term:
            params["search"] = search_term
        # Only include user_id if it's not None (since we build different queries based on user_id)
        if user_id is not None:
            params["user_id"] = normalize_user_id(user_id)

        result = await session.execute(text(final_query), params)
        return list(result.all())

    @staticmethod
    async def delete_content(
        content_type: ContentType,
        content_id: str,
        current_user_id: UUID | None = None,
    ) -> None:
        """Delete content by type and ID."""
        from src.books.services import delete_book
        from src.courses.services.course_service import CourseService
        from src.flashcards.service import delete_deck
        from src.videos.service import video_service

        async with async_session_maker() as session:
            if content_type == ContentType.BOOK:
                await delete_book(UUID(content_id))
            elif content_type == ContentType.YOUTUBE:
                await video_service.delete_video(session, content_id)
            elif content_type == ContentType.FLASHCARDS:
                await delete_deck(UUID(content_id))
            elif content_type == ContentType.ROADMAP:
                course_service = CourseService(session, current_user_id)
                await course_service.delete_course(UUID(content_id))
            else:
                error_msg = f"Unsupported content type: {content_type}"
                raise ValueError(error_msg)
