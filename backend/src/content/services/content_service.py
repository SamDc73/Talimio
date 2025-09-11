"""Main content service."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentListResponse, ContentType

# Progress calculation imports removed - progress now fetched separately
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService

# UserContext removed - using UUID directly
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
        # Use user ID for user-specific filtering
        effective_user_id = user_id

        # Use provided session or create a new one
        if self._session:
            session = self._session
            queries: list[str] = []
            needs_user_id = False

            queries, needs_user_id = QueryBuilderService.build_content_queries(
                content_type, search, include_archived, effective_user_id
            )

            if not queries:
                return ContentListResponse(items=[], total=0, page=page, per_page=page_size)

            combined_query = " UNION ALL ".join(f"({q})" for q in queries)
            total = await QueryBuilderService.get_total_count(session, combined_query, search_term, effective_user_id)
            rows = await self.get_paginated_results(
                session, combined_query, search_term, page_size, offset, effective_user_id
            )
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
            needs_user_id = False

            queries, needs_user_id = QueryBuilderService.build_content_queries(
                content_type, search, include_archived, effective_user_id
            )

            if not queries:
                return ContentListResponse(items=[], total=0, page=page, per_page=page_size)

            combined_query = " UNION ALL ".join(f"({q})" for q in queries)
            total = await QueryBuilderService.get_total_count(session, combined_query, search_term, effective_user_id)
            rows = await self.get_paginated_results(
                session, combined_query, search_term, page_size, offset, effective_user_id
            )
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

    async def delete_content(
        self,
        content_type: ContentType,
        content_id: str,
        user_id: UUID,
    ) -> None:
        """Delete content by type and ID using unified service pattern."""
        from src.books.facade import BooksFacade
        from src.courses.facade import CoursesFacade
        from src.flashcards.service import delete_deck
        from src.videos.service import VideoService

        # Use provided session or create a new one
        if self._session:
            session = self._session
            own_session = False
        else:
            session = await async_session_maker().__aenter__()
            own_session = True

        try:
            if content_type == ContentType.BOOK:
                books_facade = BooksFacade()
                await books_facade.delete_book(session, UUID(content_id), user_id)
            elif content_type == ContentType.YOUTUBE:
                video_service = VideoService()
                await video_service.delete_video(session, content_id, user_id)
            elif content_type == ContentType.FLASHCARDS:
                # Note: Flashcards still uses old pattern, needs user_id validation
                await delete_deck(UUID(content_id), user_id)
            elif content_type == ContentType.COURSE:
                courses_facade = CoursesFacade()
                await courses_facade.delete_course(session, UUID(content_id), user_id)
            else:
                error_msg = f"Unsupported content type: {content_type}"
                raise ValueError(error_msg)

            # Always commit the deletion to persist changes
            await session.commit()
        finally:
            # Close session if we created it
            if own_session:
                await session.__aexit__(None, None, None)
