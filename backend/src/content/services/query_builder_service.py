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
        queries = []
        needs_user_id = False

        if not content_type or content_type == ContentType.YOUTUBE:
            queries.append(QueryBuilderService._get_video_query(search, include_archived))

        if not content_type or content_type == ContentType.FLASHCARDS:
            queries.append(QueryBuilderService._get_flashcard_query(search, include_archived))

        if not content_type or content_type == ContentType.BOOK:
            queries.append(QueryBuilderService._get_book_query(search, include_archived, user_id))
            if user_id:
                needs_user_id = True

        if not content_type or content_type in (ContentType.ROADMAP, ContentType.COURSE):
            queries.append(QueryBuilderService._get_roadmap_query(search, include_archived))
            needs_user_id = True

        return queries, needs_user_id

    @staticmethod
    def _get_video_query(search: str | None, include_archived: bool = False) -> str:
        """Get SQL query for videos."""
        return QueryBuilderService.get_youtube_query(search, archived_only=False, include_archived=include_archived)

    @staticmethod
    def get_youtube_query(search: str | None, archived_only: bool = False, include_archived: bool = False) -> str:
        """Get SQL query for videos."""
        query = """
            SELECT
                v.uuid::text as id,
                v.title,
                COALESCE(v.description, '') as description,
                'youtube' as type,
                COALESCE(v.updated_at, v.created_at) as last_accessed,
                v.created_at,
                v.tags,
                v.channel as extra1,
                v.thumbnail_url as extra2,
                CASE
                    WHEN chapter_stats.total_chapters > 0 THEN
                        (chapter_stats.completed_chapters * 100.0 / chapter_stats.total_chapters)
                    ELSE
                        COALESCE(v.completion_percentage, 0)
                END as progress,
                COALESCE(v.duration, 0) as count1,
                0 as count2,
                COALESCE(v.archived, false) as archived,
                NULL::text as toc_progress
            FROM videos v
            LEFT JOIN (
                SELECT
                    video_uuid,
                    COUNT(*) as total_chapters,
                    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_chapters
                FROM video_chapters
                GROUP BY video_uuid
            ) chapter_stats ON v.uuid = chapter_stats.video_uuid
        """

        # Build WHERE clause
        where_conditions = []
        if archived_only:
            where_conditions.append("v.archived = true")
        elif not include_archived:
            where_conditions.append("(v.archived = false OR v.archived IS NULL)")
        # If include_archived is True, don't add any archive filter (show all)

        if search:
            where_conditions.append("(v.title ILIKE :search OR v.channel ILIKE :search)")

        if where_conditions:
            query += " WHERE " + " AND ".join(where_conditions)

        return query

    @staticmethod
    def _get_flashcard_query(search: str | None, include_archived: bool = False) -> str:
        """Get SQL query for flashcards."""
        return QueryBuilderService.get_flashcards_query(search, archived_only=False, include_archived=include_archived)

    @staticmethod
    def get_flashcards_query(search: str | None, archived_only: bool = False, include_archived: bool = False) -> str:
        """Get SQL query for flashcards."""
        query = """
            SELECT
                id::text,
                name as title,
                COALESCE(description, '') as description,
                'flashcards' as type,
                COALESCE(updated_at, created_at) as last_accessed,
                created_at,
                tags,
                '' as extra1,
                '' as extra2,
                0 as progress,
                (SELECT COUNT(*) FROM flashcard_cards WHERE deck_id = flashcard_decks.id) as count1,
                0 as count2,
                COALESCE(archived, false) as archived,
                NULL::text as toc_progress
            FROM flashcard_decks
        """

        # Build WHERE clause
        where_conditions = []
        if archived_only:
            where_conditions.append("archived = true")
        elif not include_archived:
            where_conditions.append("(archived = false OR archived IS NULL)")
        # If include_archived is True, don't add any archive filter (show all)

        if search:
            where_conditions.append("(name ILIKE :search OR description ILIKE :search)")

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
        """Get SQL query for books."""
        # If user_id is provided, filter book_progress by user_id
        # FIX: user_id is stored as UUID in the database (not VARCHAR)
        user_filter = "AND user_id = :user_id" if user_id else ""

        query = f"""
            SELECT
                b.id::text,
                b.title,
                COALESCE(b.description, '') as description,
                'book' as type,
                COALESCE(b.updated_at, b.created_at) as last_accessed,
                b.created_at,
                b.tags,
                b.author as extra1,
                '' as extra2,
                COALESCE(
                    (SELECT progress_percentage
                     FROM book_progress
                     WHERE book_id = b.id {user_filter}
                     ORDER BY updated_at DESC
                     LIMIT 1), 0
                )::int as progress,
                COALESCE(b.total_pages, 0) as count1,
                COALESCE(
                    (SELECT current_page
                     FROM book_progress
                     WHERE book_id = b.id {user_filter}
                     ORDER BY updated_at DESC
                     LIMIT 1), 1
                ) as count2,
                COALESCE(b.archived, false) as archived,
                COALESCE(
                    (SELECT toc_progress::text
                     FROM book_progress
                     WHERE book_id = b.id {user_filter}
                     ORDER BY updated_at DESC
                     LIMIT 1), '{{}}')::text as toc_progress
            FROM books b
        """
        # Build WHERE clause
        where_conditions = []
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
    def _get_roadmap_query(search: str | None, include_archived: bool = False) -> str:
        """Get SQL query for roadmaps."""
        return QueryBuilderService.get_roadmaps_query(
            search, archived_only=False, include_archived=include_archived
        )

    @staticmethod
    def get_roadmaps_query(
        search: str | None, archived_only: bool = False, include_archived: bool = False
    ) -> str:
        """Get SQL query for roadmaps. Progress will be calculated separately using CourseProgressService."""
        # Simplified query - progress is calculated post-query using CourseProgressService for DRY
        query = """
            SELECT
                r.id::text,
                r.title,
                COALESCE(r.description, '') as description,
                'roadmap' as type,
                COALESCE(r.updated_at, r.created_at) as last_accessed,
                r.created_at,
                '[]' as tags,
                '' as extra1,
                '' as extra2,
                0 as progress,
                -- Total lessons (leaf nodes)
                (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id AND parent_id IS NOT NULL) as count1,
                0 as count2,
                COALESCE(r.archived, false) as archived,
                NULL::text as toc_progress
            FROM roadmaps r
        """

        # Build WHERE clause
        where_conditions = []
        if archived_only:
            where_conditions.append("r.archived = true")
        elif not include_archived:
            where_conditions.append("(r.archived = false OR r.archived IS NULL)")
        # If include_archived is True, don't add any archive filter (show all)

        if search:
            where_conditions.append("(r.title ILIKE :search OR r.description ILIKE :search)")

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
        # Only include user_id if it's not None (since we build different queries based on user_id)
        if user_id is not None:
            params["user_id"] = user_id
        count_result = await session.execute(
            text(count_query),
            params,
        )
        return count_result.scalar() or 0
