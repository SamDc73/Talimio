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

        if not content_type or content_type == ContentType.FLASHCARDS:
            queries.append(QueryBuilderService._get_flashcard_query(search, include_archived, user_id))
            if user_id:
                needs_user_id = True

        if not content_type or content_type == ContentType.BOOK:
            queries.append(QueryBuilderService._get_book_query(search, include_archived, user_id))
            if user_id:
                needs_user_id = True

        if not content_type or content_type == ContentType.COURSE:
            queries.append(QueryBuilderService._get_roadmap_query(search, include_archived, user_id))
            if user_id:
                needs_user_id = True

        return queries, needs_user_id

    @staticmethod
    def _get_video_query(search: str | None, include_archived: bool = False, user_id: UUID | None = None) -> str:
        """Get SQL query for videos."""
        # If DEFAULT_USER_ID, show all videos (for demo/development)
        effective_user_id = user_id if str(user_id) != "00000000-0000-0000-0000-000000000001" else None
        return QueryBuilderService.get_youtube_query(search, archived_only=False, include_archived=include_archived, user_id=effective_user_id)

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
                v.tags,
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
    def _get_flashcard_query(search: str | None, include_archived: bool = False, user_id: UUID | None = None) -> str:
        """Get SQL query for flashcards."""
        # If DEFAULT_USER_ID, show all flashcards (for demo/development)
        effective_user_id = user_id if str(user_id) != "00000000-0000-0000-0000-000000000001" else None
        return QueryBuilderService.get_flashcards_query(search, archived_only=False, include_archived=include_archived, user_id=effective_user_id)

    @staticmethod
    def get_flashcards_query(search: str | None, archived_only: bool = False, include_archived: bool = False, user_id: UUID | None = None) -> str:
        """Get SQL query for flashcards with user filtering."""
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
                NULL::text as toc_progress,
                NULL::text as table_of_contents
            FROM flashcard_decks
        """

        # Build WHERE clause
        where_conditions = []

        # CRITICAL: Filter by user_id since flashcards are user-specific
        # Skip filtering if no user_id (for demo/development with DEFAULT_USER_ID)
        if user_id:
            where_conditions.append("user_id = :user_id")

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
        # If DEFAULT_USER_ID, show all books (for demo/development)
        effective_user_id = user_id if str(user_id) != "00000000-0000-0000-0000-000000000001" else None
        return QueryBuilderService.get_books_query(
            search, archived_only=False, include_archived=include_archived, user_id=effective_user_id
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
                b.tags,
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

        # CRITICAL: Filter by user_id since books are user-specific
        # Skip filtering if no user_id (for demo/development with DEFAULT_USER_ID)
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
    def _get_roadmap_query(search: str | None, include_archived: bool = False, user_id: UUID | None = None) -> str:
        """Get SQL query for roadmaps."""
        # If DEFAULT_USER_ID, show all roadmaps (for demo/development)
        effective_user_id = user_id if str(user_id) != "00000000-0000-0000-0000-000000000001" else None
        return QueryBuilderService.get_roadmaps_query(
            search, archived_only=False, include_archived=include_archived, user_id=effective_user_id
        )

    @staticmethod
    def get_roadmaps_query(
        search: str | None, archived_only: bool = False, include_archived: bool = False, user_id: UUID | None = None
    ) -> str:
        """Get SQL query for roadmaps WITHOUT progress (optimized for performance)."""
        # No more progress JOINs or subqueries - progress is fetched separately
        query = """
            SELECT
                r.id::text,
                r.title,
                COALESCE(r.description, '') as description,
                'roadmap' as type,
                COALESCE(r.updated_at, r.created_at) as last_accessed,
                r.created_at,
                COALESCE(r.tags, '[]') as tags,
                '' as extra1,
                '' as extra2,
                0 as progress,
                -- Total lessons (leaf nodes)
                (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id AND parent_id IS NOT NULL) as count1,
                0 as count2,
                COALESCE(r.archived, false) as archived,
                NULL::text as toc_progress,
                NULL::text as table_of_contents
            FROM roadmaps r
        """

        # Build WHERE clause
        where_conditions = []

        # CRITICAL: Filter by user_id since roadmaps are user-specific
        # Skip filtering if no user_id (for demo/development with DEFAULT_USER_ID)
        if user_id:
            where_conditions.append("r.user_id = :user_id")

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
