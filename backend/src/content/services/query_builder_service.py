"""Query builder service for content operations."""

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentType


logger = logging.getLogger(__name__)


class QueryBuilderService:
    """Service for building SQL queries for content operations."""

    @staticmethod
    def build_content_queries(
        content_type: ContentType | None,
        search: str | None,
        include_archived: bool = False,
        user_id: UUID | None = None,
    ) -> tuple[list[str], bool]:
        """Build SQL queries for different content types. Returns queries and whether user_id is needed."""
        queries: list[str] = []
        needs_user_id = False

        if not content_type or content_type == ContentType.YOUTUBE:
            queries.append(QueryBuilderService._get_video_query(search, include_archived, user_id))
            if user_id:
                needs_user_id = True


        if not content_type or content_type == ContentType.BOOK:
            queries.append(QueryBuilderService._get_book_query(search, include_archived, user_id))
            if user_id:
                needs_user_id = True

        if not content_type or content_type == ContentType.COURSE:
            queries.append(
                QueryBuilderService.get_courses_query(
                    search, archived_only=False, include_archived=include_archived, user_id=user_id
                )
            )
            if user_id:
                needs_user_id = True

        return queries, needs_user_id

    @staticmethod
    def _get_video_query(search: str | None, include_archived: bool = False, user_id: UUID | None = None) -> str:
        """Get SQL query for videos."""
        return QueryBuilderService.get_youtube_query(
            search, archived_only=False, include_archived=include_archived, user_id=user_id
        )

    @staticmethod
    def get_youtube_query(
        search: str | None,
        archived_only: bool = False,
        include_archived: bool = False,
        user_id: UUID | None = None,
    ) -> str:
        """Get SQL query for videos WITHOUT progress (optimized for performance)."""
        # No more progress JOINs - progress is fetched separately
        query = """
            SELECT
                v.id::text as id,
                v.title,
                COALESCE(v.description, '') as description,
                'youtube' as type,
                COALESCE(v.updated_at, v.created_at) as last_accessed,
                v.created_at,
                COALESCE(v.tags, '[]') as tags,
                v.channel as extra1,
                v.thumbnail_url as extra2,
                0 as progress,
                COALESCE(v.duration, 0) as count1,
                0 as count2,
                COALESCE(v.archived, false) as archived,
                NULL::text as toc_progress,
                NULL::text as table_of_contents
            FROM videos v
        """

        # Build WHERE clause
        where_conditions = []
        if archived_only:
            where_conditions.append("v.archived = true")
        elif not include_archived:
            where_conditions.append("(v.archived = false OR v.archived IS NULL)")

        if search:
            where_conditions.append("(v.title ILIKE :search OR v.channel ILIKE :search)")

        # Add user_id filter if provided
        if user_id:
            where_conditions.append("v.user_id = :user_id")

        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        return query


    @staticmethod
    def _get_book_query(search: str | None, include_archived: bool = False, user_id: UUID | None = None) -> str:
        """Get SQL query for books."""
        return QueryBuilderService.get_books_query(
            search, archived_only=False, include_archived=include_archived, user_id=user_id
        )

    @staticmethod
    def get_books_query(
        search: str | None, archived_only: bool = False, include_archived: bool = False, user_id: UUID | None = None
    ) -> str:
        """Get SQL query for books WITHOUT progress (optimized for performance)."""
        # No more progress JOINs - progress is fetched separately
        query = """
            SELECT
                b.id::text,
                b.title,
                COALESCE(b.description, '') as description,
                'book' as type,
                COALESCE(b.updated_at, b.created_at) as last_accessed,
                b.created_at,
                COALESCE(b.tags, '[]') as tags,
                b.author as extra1,
                '' as extra2,
                0 as progress,
                COALESCE(b.total_pages, 0) as count1,
                0 as count2,
                COALESCE(b.archived, false) as archived,
                '{}'::text as toc_progress,
                NULL::text as table_of_contents
            FROM books b
        """
        # Build WHERE clause
        where_conditions = []

        # Filter by user_id since books are user-specific
        if user_id:
            where_conditions.append("b.user_id = :user_id")

        if archived_only:
            where_conditions.append("b.archived = true")
        elif not include_archived:
            where_conditions.append("(b.archived = false OR b.archived IS NULL)")
        # If include_archived is True, don't add any archive filter (show all)

        if search:
            where_conditions.append("(b.title ILIKE :search OR b.author ILIKE :search)")

        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        return query


    @staticmethod
    def get_courses_query(
        search: str | None,
        archived_only: bool = False,
        include_archived: bool = False,
        user_id: UUID | None = None,
    ) -> str:
        """Get SQL query for courses WITHOUT progress (optimized for performance)."""
        query = """
            SELECT
                c.id::text,
                c.title,
                COALESCE(c.description, '') as description,
                'course' as type,
                COALESCE(c.updated_at, c.created_at) as last_accessed,
                c.created_at,
                COALESCE(c.tags, '[]') as tags,
                '' as extra1,
                '' as extra2,
                0 as progress,
                (
                    SELECT COUNT(*)
                    FROM lessons l
                    WHERE l.course_id = c.id
                ) as count1,
                (
                    SELECT COUNT(DISTINCT l.module_name)
                    FROM lessons l
                    WHERE l.course_id = c.id AND l.module_name IS NOT NULL
                ) as count2,
                COALESCE(c.archived, false) as archived,
                NULL::text as toc_progress,
                NULL::text as table_of_contents
            FROM courses c
        """

        where_conditions: list[str] = []

        if user_id:
            where_conditions.append("c.user_id = :user_id")

        if archived_only:
            where_conditions.append("c.archived = true")
        elif not include_archived:
            where_conditions.append("(c.archived = false OR c.archived IS NULL)")

        if search:
            where_conditions.append("(c.title ILIKE :search OR c.description ILIKE :search)")

        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        return query

    @staticmethod
    async def get_total_count(
        session: AsyncSession, combined_query: str, search_term: str | None, user_id: UUID | None = None
    ) -> int:
        """Get total count of results."""
        count_query = f"SELECT COUNT(*) FROM ({combined_query}) as combined"
        params = {}
        if search_term:
            params["search"] = search_term
        # Include user_id if provided
        if user_id is not None:
            params["user_id"] = user_id
        count_result = await session.execute(
            text(count_query),
            params,
        )
        return count_result.scalar() or 0
