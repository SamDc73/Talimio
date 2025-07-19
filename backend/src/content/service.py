"""Ultra-fast content service with minimal queries."""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import (
    BookContent,
    ContentListResponse,
    ContentType,
    CourseContent,
    FlashcardContent,
    RoadmapContent,
    YoutubeContent,
)
from src.core.user_context import get_effective_user_id
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


def _safe_parse_tags(tags_json: str | None) -> list[str]:
    """Safely parse tags from JSON string."""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


async def list_content_fast(
    search: str | None = None,
    content_type: ContentType | None = None,
    page: int = 1,
    page_size: int = 20,
    include_archived: bool = False,
    current_user_id: str | None = None,
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
    try:
        effective_user_id = get_effective_user_id(current_user_id)
    except ValueError:
        # No user authenticated in multi-user mode - show content without progress
        effective_user_id = None
    # For content listing, we don't require authentication
    # If no user is provided, we'll show content with 0% progress
    try:
        effective_user_id = get_effective_user_id(current_user_id)
    except ValueError:
        # No user authenticated in multi-user mode - show content without progress
        effective_user_id = None

    async with async_session_maker() as session:
        logger.info(
            f"🔍 list_content_fast called with include_archived={include_archived}, search={search}, content_type={content_type}"
        )

        queries, needs_user_id = _build_content_queries(content_type, search, include_archived, effective_user_id)

        if not queries:
            return ContentListResponse(items=[], total=0, page=page, page_size=page_size)

        combined_query = " UNION ALL ".join(f"({q})" for q in queries)
        total = await _get_total_count(session, combined_query, search_term, effective_user_id)
        rows = await _get_paginated_results(session, combined_query, search_term, page_size, offset, effective_user_id)
        items = _transform_rows_to_items(rows)

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


async def _calculate_course_progress(session, items: list[Any], user_id: str) -> list[Any]:
    """Calculate accurate course progress using CourseProgressService (DRY)."""
    from uuid import UUID

    from src.courses.services.course_progress_service import CourseProgressService

    # Filter for course items only (roadmap type in DB, but shows as course in enum)
    course_items = [item for item in items if hasattr(item, "type") and str(item.type) in ("roadmap", "course", "ContentType.COURSE")]

    if not course_items:
        return items

    # Initialize progress service
    progress_service = CourseProgressService(session, user_id)

    # Calculate progress for each course using our DRY service
    for item in course_items:
        try:
            course_id = UUID(item.id)
            user_uuid = UUID(user_id)

            # Use our DRY CourseProgressService
            progress = await progress_service.get_course_progress_percentage(course_id, user_uuid)
            stats = await progress_service.get_lesson_completion_stats(course_id, user_uuid)

            # Update the item's progress
            item.progress = float(progress)
            if hasattr(item, "completed_lessons"):
                item.completed_lessons = stats["completed_lessons"]

        except (ValueError, Exception):
            # Keep original progress (0) if there's an error
            pass

    return items


async def _calculate_book_progress(session, items: list[Any], user_id: str) -> list[Any]:
    """Calculate accurate book progress using BookProgressService (matching course pattern)."""
    from uuid import UUID

    from src.books.services.book_progress_service import BookProgressService

    # Filter for book items only
    book_items = [item for item in items if hasattr(item, "type") and str(item.type) == "book"]

    if not book_items:
        return items

    # Initialize progress service
    progress_service = BookProgressService(session, user_id)

    # Calculate progress for each book using TOC-based progress
    for item in book_items:
        try:
            book_id = UUID(item.id)

            # Use our BookProgressService for TOC-based progress
            progress = await progress_service.get_book_toc_progress_percentage(book_id, user_id)
            stats = await progress_service.get_toc_completion_stats(book_id, user_id)

            # Update the item's progress with TOC-based calculation
            item.progress = float(progress)

            # Store additional stats for frontend if needed
            if hasattr(item, "completed_sections"):
                item.completed_sections = stats["completed_sections"]
            if hasattr(item, "total_sections"):
                item.total_sections = stats["total_sections"]

        except (ValueError, Exception) as e:
            # Keep original progress (page-based) if there's an error
            logger.debug(f"Error calculating TOC progress for book {item.id}: {e}")

    return items


def _build_content_queries(
    content_type: ContentType | None, search: str | None, include_archived: bool = False, user_id: str | None = None
) -> tuple[list[str], bool]:
    """Build SQL queries for different content types. Returns queries and whether user_id is needed."""
    queries = []
    needs_user_id = False

    if not content_type or content_type == ContentType.YOUTUBE:
        queries.append(_get_video_query(search, include_archived))

    if not content_type or content_type == ContentType.FLASHCARDS:
        queries.append(_get_flashcard_query(search, include_archived))

    if not content_type or content_type == ContentType.BOOK:
        queries.append(_get_book_query(search, include_archived, user_id))
        if user_id:
            needs_user_id = True

    if not content_type or content_type in (ContentType.ROADMAP, ContentType.COURSE):
        queries.append(_get_roadmap_query(search, include_archived, user_id))
        needs_user_id = True

    return queries, needs_user_id


def _get_video_query(search: str | None, include_archived: bool = False) -> str:
    """Get SQL query for videos."""
    return _get_youtube_query(search, archived_only=False, include_archived=include_archived)


def _get_youtube_query(search: str | None, archived_only: bool = False, include_archived: bool = False) -> str:
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


def _get_flashcard_query(search: str | None, include_archived: bool = False) -> str:
    """Get SQL query for flashcards."""
    return _get_flashcards_query(search, archived_only=False, include_archived=include_archived)


def _get_flashcards_query(search: str | None, archived_only: bool = False, include_archived: bool = False) -> str:
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


def _get_book_query(search: str | None, include_archived: bool = False, user_id: str | None = None) -> str:
    """Get SQL query for books."""
    return _get_books_query(search, archived_only=False, include_archived=include_archived, user_id=user_id)


def _get_books_query(search: str | None, archived_only: bool = False, include_archived: bool = False, user_id: str | None = None) -> str:
    """Get SQL query for books."""
    # If user_id is provided, filter book_progress by user_id
    # user_id is stored as VARCHAR in the database
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


def _get_roadmap_query(search: str | None, include_archived: bool = False, user_id: str | None = None) -> str:
    """Get SQL query for roadmaps."""
    return _get_roadmaps_query(search, archived_only=False, include_archived=include_archived, user_id=user_id)


def _get_roadmaps_query(search: str | None, archived_only: bool = False, include_archived: bool = False, user_id: str | None = None) -> str:
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


async def _get_total_count(session: AsyncSession, combined_query: str, search_term: str | None, user_id: str | None = None) -> int:
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


async def _get_paginated_results(
    session: AsyncSession,
    combined_query: str,
    search_term: str | None,
    page_size: int,
    offset: int,
    user_id: str | None = None,
) -> list[Any]:
    """Get paginated results."""
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
        params["user_id"] = user_id

    result = await session.execute(text(final_query), params)
    return list(result.all())


def _transform_rows_to_items(rows: list[Any]) -> list[Any]:
    """Transform database rows to content items."""
    items: list[Any] = []
    for row in rows:
        if row.type == "youtube":
            items.append(_create_youtube_content(row))
        elif row.type == "flashcards":
            items.append(_create_flashcard_content(row))
        elif row.type == "book":
            items.append(_create_book_content(row))
        elif row.type == "roadmap":
            items.append(_create_roadmap_content(row))
    return items


def _create_youtube_content(row: Any) -> YoutubeContent:
    """Create YoutubeContent from row data."""
    return YoutubeContent(
        id=row.id,
        title=row.title,
        description=row.description,
        channelName=row.extra1 or "",
        duration=row.count1,
        thumbnailUrl=row.extra2,
        lastAccessedDate=row.last_accessed,
        createdDate=row.created_at,
        progress=row.progress,
        tags=_safe_parse_tags(row.tags),
        archived=row.archived,
    )


def _create_flashcard_content(row: Any) -> FlashcardContent:
    """Create FlashcardContent from row data."""
    return FlashcardContent(
        id=row.id,
        title=row.title,
        description=row.description,
        cardCount=row.count1,
        dueCount=0,
        lastAccessedDate=row.last_accessed,
        createdDate=row.created_at,
        progress=row.progress,
        tags=_safe_parse_tags(row.tags),
        archived=row.archived,
    )


def _create_book_content(row: Any) -> BookContent:
    """Create BookContent from row data."""
    # Parse toc_progress from JSON string
    toc_progress = None
    if hasattr(row, "toc_progress") and row.toc_progress:
        try:
            toc_progress = json.loads(row.toc_progress)
        except (json.JSONDecodeError, TypeError):
            toc_progress = {}

    return BookContent(
        id=row.id,
        title=row.title,
        description=row.description,
        author=row.extra1 or "",
        pageCount=row.count1,
        currentPage=row.count2,
        lastAccessedDate=row.last_accessed,
        createdDate=row.created_at,
        progress=row.progress,
        tags=_safe_parse_tags(row.tags),
        archived=row.archived,
        tocProgress=toc_progress,
    )


def _create_roadmap_content(row: Any) -> RoadmapContent:
    """Create RoadmapContent from row data."""
    # Return CourseContent instead of RoadmapContent for frontend compatibility
    return CourseContent(
        id=row.id,
        title=row.title,
        description=row.description,
        nodeCount=row.count1,
        completedNodes=row.count2,
        lastAccessedDate=row.last_accessed,
        createdDate=row.created_at,
        progress=row.progress,
        tags=[],
        archived=row.archived,
    )


async def archive_content(content_type: ContentType, content_id: str) -> None:
    """Archive content by type and ID."""
    table_map = {
        ContentType.BOOK: "books",
        ContentType.YOUTUBE: "videos",
        ContentType.FLASHCARDS: "flashcard_decks",
        ContentType.ROADMAP: "roadmaps",
        ContentType.COURSE: "roadmaps",  # Alias for roadmap
    }

    table_name = table_map.get(content_type)
    if not table_name:
        msg = f"Unsupported content type: {content_type}"
        logger.error(msg)
        raise ValueError(msg)

    logger.info(f"🗃️ Archiving {content_type} {content_id} in table {table_name}")

    async with async_session_maker() as session:
        # Handle different ID column names
        id_column = "uuid" if content_type == ContentType.YOUTUBE else "id"

        query = f"""
            UPDATE {table_name}
            SET archived = true, archived_at = :archived_at
            WHERE {id_column} = :content_id
        """

        logger.info(f"🔍 Executing query: {query}")
        logger.info(f"🔍 With params: content_id={content_id}, archived_at={datetime.now(UTC)}")

        result = await session.execute(text(query), {"content_id": content_id, "archived_at": datetime.now(UTC)})
        affected_rows = result.rowcount
        await session.commit()

        logger.info(f"📊 Archive operation affected {affected_rows} rows")

        if affected_rows == 0:
            logger.warning(f"⚠️ No rows were updated - content {content_id} may not exist")
        else:
            logger.info(f"✅ Successfully archived {content_id}")


async def unarchive_content(content_type: ContentType, content_id: str) -> None:
    """Unarchive content by type and ID."""
    table_map = {
        ContentType.BOOK: "books",
        ContentType.YOUTUBE: "videos",
        ContentType.FLASHCARDS: "flashcard_decks",
        ContentType.ROADMAP: "roadmaps",
        ContentType.COURSE: "roadmaps",  # Alias for roadmap
    }

    table_name = table_map.get(content_type)
    if not table_name:
        msg = f"Unsupported content type: {content_type}"
        logger.error(msg)
        raise ValueError(msg)

    logger.info(f"📤 Unarchiving {content_type} {content_id} in table {table_name}")

    async with async_session_maker() as session:
        try:
            # Handle different ID column names
            id_column = "uuid" if content_type == ContentType.YOUTUBE else "id"

            query = f"""
                UPDATE {table_name}
                SET archived = false, archived_at = NULL
                WHERE {id_column} = :content_id
            """

            logger.info(f"🔍 Executing unarchive query: {query}")
            logger.info(f"🔍 With params: content_id={content_id}")

            result = await session.execute(text(query), {"content_id": content_id})
            affected_rows = result.rowcount
            await session.commit()

            logger.info(f"📊 Unarchive operation affected {affected_rows} rows")

            if affected_rows == 0:
                logger.warning(f"⚠️ No rows were updated - content {content_id} may not exist")
            else:
                logger.info(f"✅ Successfully unarchived {content_id}")

        except Exception:
            logger.exception(
                "💥 Database error in unarchive_content. Query: %s, Params: content_id=%s", query, content_id
            )
            await session.rollback()
            raise


async def list_archived_content(
    search: str | None = None,
    content_type: ContentType | None = None,
    page: int = 1,
    page_size: int = 20,
    current_user_id: str | None = None,
) -> ContentListResponse:
    """
    List only archived content across different types.

    Similar to list_content_fast but filters for archived = true.
    """
    offset = (page - 1) * page_size
    search_term = f"%{search}%" if search else None
    # For content listing, we don't require authentication
    # If no user is provided, we'll show content with 0% progress
    try:
        effective_user_id = get_effective_user_id(current_user_id)
    except ValueError:
        # No user authenticated in multi-user mode - show content without progress
        effective_user_id = None

    # Construct the combined query with archived filter
    if content_type:
        if content_type == ContentType.YOUTUBE:
            combined_query = _get_youtube_query(search, archived_only=True)
        elif content_type == ContentType.FLASHCARDS:
            combined_query = _get_flashcards_query(search, archived_only=True)
        elif content_type == ContentType.BOOK:
            combined_query = _get_books_query(search, archived_only=True)
        elif content_type == ContentType.ROADMAP:
            combined_query = _get_roadmaps_query(search, archived_only=True, user_id=effective_user_id)
        else:
            msg = f"Unsupported content type: {content_type}"
            raise ValueError(msg)
    else:
        # Union all content types with archived filter
        combined_query = f"""
            {_get_youtube_query(search, archived_only=True)}
            UNION ALL
            {_get_flashcards_query(search, archived_only=True)}
            UNION ALL
            {_get_books_query(search, archived_only=True)}
            UNION ALL
            {_get_roadmaps_query(search, archived_only=True, user_id=effective_user_id)}
        """

    async with async_session_maker() as session:
        # Get total count and paginated results
        total = await _get_total_count(session, combined_query, search_term, effective_user_id)
        rows = await _get_paginated_results(session, combined_query, search_term, page_size, offset, effective_user_id)

        # Transform rows to content items
        items = _transform_rows_to_items(rows)

    return ContentListResponse(
        items=items,
        total=total,
        page=page,
        pageSize=page_size,
    )


async def get_content_stats() -> dict[str, Any]:
    """Get dashboard statistics for all content types."""
    async with async_session_maker() as session:
        # Get counts for each content type
        stats_query = """
            SELECT
                'books' as type,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE archived = true) as archived
            FROM books
            UNION ALL
            SELECT
                'videos' as type,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE archived = true) as archived
            FROM videos
            UNION ALL
            SELECT
                'flashcard_decks' as type,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE archived = true) as archived
            FROM flashcard_decks
            UNION ALL
            SELECT
                'roadmaps' as type,
                COUNT(*) as total,
                COUNT(*) FILTER (WHERE archived = true) as archived
            FROM roadmaps
        """

        result = await session.execute(text(stats_query))
        rows = result.all()

        stats = {"totalContent": 0, "totalArchived": 0, "byType": {}}

        type_mapping = {"books": "book", "videos": "youtube", "flashcard_decks": "flashcards", "roadmaps": "roadmap"}

        for row in rows:
            content_type = type_mapping.get(row.type, row.type)
            stats["byType"][content_type] = {
                "total": row.total,
                "archived": row.archived,
                "active": row.total - row.archived,
            }
            stats["totalContent"] += row.total
            stats["totalArchived"] += row.archived

        stats["totalActive"] = stats["totalContent"] - stats["totalArchived"]

        return stats


async def delete_content(content_type: ContentType, content_id: str) -> None:
    """Delete content by type and ID using proper ORM cascade deletion."""
    from uuid import UUID

    # Import the models for proper ORM deletion
    if content_type == ContentType.BOOK:
        from src.books.models import Book as ModelClass
    elif content_type == ContentType.YOUTUBE:
        from src.videos.models import Video as ModelClass
    elif content_type == ContentType.FLASHCARDS:
        from src.flashcards.models import FlashcardDeck as ModelClass
    elif content_type in (ContentType.ROADMAP, ContentType.COURSE):
        from src.courses.models import Roadmap as ModelClass
    else:
        msg = f"Unsupported content type: {content_type}"
        raise ValueError(msg)

    async with async_session_maker() as session:
        # Handle different ID column names and types
        if content_type == ContentType.YOUTUBE:
            # Videos use uuid column, need to query by uuid field
            from sqlalchemy import select

            stmt = select(ModelClass).where(ModelClass.uuid == content_id)
            result = await session.execute(stmt)
            content_obj = result.scalar_one_or_none()
        else:
            # Convert string ID to UUID for other content types
            try:
                uuid_id = UUID(content_id)
                content_obj = await session.get(ModelClass, uuid_id)
            except ValueError as ve:
                msg = f"Invalid ID format: {content_id}"
                raise ValueError(msg) from ve

        if not content_obj:
            msg = f"Content with ID {content_id} not found"
            raise ValueError(msg)

        # Special handling for roadmaps to fix foreign key constraint issues
        if content_type in (ContentType.ROADMAP, ContentType.COURSE):
            # First, delete all nodes that reference this roadmap in correct order
            # Delete child nodes first, then parent nodes to avoid foreign key violations
            await session.execute(
                text("""
                    WITH RECURSIVE node_hierarchy AS (
                        -- Find leaf nodes (no children)
                        SELECT id, parent_id, 0 as level
                        FROM nodes
                        WHERE roadmap_id = :roadmap_id
                        AND id NOT IN (SELECT parent_id FROM nodes WHERE parent_id IS NOT NULL AND roadmap_id = :roadmap_id)

                        UNION ALL

                        -- Find parent nodes
                        SELECT n.id, n.parent_id, nh.level + 1
                        FROM nodes n
                        JOIN node_hierarchy nh ON n.id = nh.parent_id
                        WHERE n.roadmap_id = :roadmap_id
                    )
                    DELETE FROM nodes WHERE id IN (SELECT id FROM node_hierarchy)
                """),
                {"roadmap_id": uuid_id},
            )

            # Now delete the roadmap itself
            await session.execute(text("DELETE FROM roadmaps WHERE id = :roadmap_id"), {"roadmap_id": uuid_id})
        else:
            # Delete using ORM to ensure proper cascade deletion for other content types
            await session.delete(content_obj)

        await session.commit()


class ContentService:
    """Service for unified content operations including progress tracking."""

    def __init__(self, session: AsyncSession):
        """Initialize the content service."""
        self.session = session

    async def get_content_progress(self, content_type: str, content_id: str | UUID, user_id: str | None = None) -> int:
        """Unified interface for getting progress across content types.
        
        Args:
            content_type: One of 'course', 'book', 'youtube', 'flashcards'
            content_id: The UUID of the content (as string or UUID)
            user_id: User ID for user-specific progress (required for courses)
            
        Returns
        -------
            Progress percentage (0-100)
        """
        from uuid import UUID

        # Convert string to UUID if needed
        if isinstance(content_id, str):
            try:
                content_id = UUID(content_id)
            except ValueError:
                # Invalid UUID format
                return 0

        if content_type == "course":
            from src.courses.services.course_progress_service import CourseProgressService
            if user_id is None:
                return 0  # Course progress requires user context
            try:
                user_uuid = UUID(user_id)
            except ValueError:
                return 0
            service = CourseProgressService(self.session, user_id)
            return await service.get_course_progress_percentage(content_id, user_uuid)

        if content_type == "book":
            from src.books.services.book_service import BookService
            service = BookService(self.session)
            return await service.get_book_progress(content_id)

        if content_type == "youtube":
            from src.videos.service import VideoService
            service = VideoService()
            return await service.get_video_progress(content_id)

        if content_type == "flashcards":
            return 0  # TODO: Implement when flashcard progress is needed

        return 0

    async def bulk_get_progress(self, items: list[tuple[str, str | UUID]], user_id: str | None = None) -> dict[str, int]:
        """Get progress for multiple items efficiently.

        Args:
            items: List of (content_type, content_id) tuples
            user_id: User ID for user-specific progress (required for courses)

        Returns
        -------
            Dictionary mapping "type:id" to progress percentage
        """
        results = {}

        # Group by type for efficient querying
        courses = [id for type, id in items if type == "course"]
        videos = [id for type, id in items if type == "youtube"]
        books = [id for type, id in items if type == "book"]

        # Process courses
        if courses and user_id:
            from src.courses.services.course_progress_service import CourseProgressService
            try:
                user_uuid = UUID(user_id)
                service = CourseProgressService(self.session, user_id)
                for course_id in courses:
                    try:
                        if isinstance(course_id, str):
                            course_uuid = UUID(course_id)
                        else:
                            course_uuid = course_id
                        progress = await service.get_course_progress_percentage(course_uuid, user_uuid)
                        results[f"course:{course_id}"] = progress
                    except (ValueError, Exception):
                        results[f"course:{course_id}"] = 0
            except ValueError:
                # Invalid user_id
                for course_id in courses:
                    results[f"course:{course_id}"] = 0

        # Process videos
        if videos:
            from src.videos.service import VideoService
            service = VideoService()
            for video_id in videos:
                try:
                    if isinstance(video_id, str):
                        video_uuid = UUID(video_id)
                    else:
                        video_uuid = video_id
                    progress = await service.get_video_progress(video_uuid)
                    results[f"youtube:{video_id}"] = progress
                except (ValueError, Exception):
                    results[f"youtube:{video_id}"] = 0

        # Process books
        if books:
            from src.books.services.book_service import BookService
            service = BookService(self.session)
            for book_id in books:
                try:
                    if isinstance(book_id, str):
                        book_uuid = UUID(book_id)
                    else:
                        book_uuid = book_id
                    progress = await service.get_book_progress(book_uuid)
                    results[f"book:{book_id}"] = progress
                except (ValueError, Exception):
                    results[f"book:{book_id}"] = 0

        return results
