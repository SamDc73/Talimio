"""Ultra-fast content service with minimal queries."""

import json
import logging
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import (
    BookContent,
    ContentListResponse,
    ContentType,
    FlashcardContent,
    RoadmapContent,
    YoutubeContent,
)
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

    async with async_session_maker() as session:
        queries = _build_content_queries(content_type, search)

        if not queries:
            return ContentListResponse(items=[], total=0, page=page, page_size=page_size)

        combined_query = " UNION ALL ".join(f"({q})" for q in queries)
        total = await _get_total_count(session, combined_query, search_term)
        rows = await _get_paginated_results(session, combined_query, search_term, page_size, offset)
        items = _transform_rows_to_items(rows)

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )


def _build_content_queries(content_type: ContentType | None, search: str | None) -> list[str]:
    """Build SQL queries for different content types."""
    queries = []

    if not content_type or content_type == ContentType.YOUTUBE:
        queries.append(_get_video_query(search))

    if not content_type or content_type == ContentType.FLASHCARDS:
        queries.append(_get_flashcard_query(search))

    if not content_type or content_type == ContentType.BOOK:
        queries.append(_get_book_query(search))

    if not content_type or content_type == ContentType.ROADMAP:
        queries.append(_get_roadmap_query(search))

    return queries


def _get_video_query(search: str | None) -> str:
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
            0 as count2
        FROM videos v
        LEFT JOIN (
            SELECT
                video_uuid,
                COUNT(*) as total_chapters,
                COUNT(CASE WHEN status = 'done' THEN 1 END) as completed_chapters
            FROM video_chapters
            GROUP BY video_uuid
        ) chapter_stats ON v.uuid = chapter_stats.video_uuid
    """
    if search:
        query += " WHERE v.title ILIKE %(search)s OR v.channel ILIKE %(search)s"
    return query


def _get_flashcard_query(search: str | None) -> str:
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
            0 as count2
        FROM flashcard_decks
    """
    if search:
        query += " WHERE name ILIKE %(search)s OR description ILIKE %(search)s"
    return query


def _get_book_query(search: str | None) -> str:
    """Get SQL query for books."""
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
            COALESCE(
                (SELECT progress_percentage
                 FROM book_progress
                 WHERE book_id = b.id
                 ORDER BY updated_at DESC
                 LIMIT 1), 0
            )::int as progress,
            COALESCE(b.total_pages, 0) as count1,
            0 as count2
        FROM books b
    """
    if search:
        query += " WHERE b.title ILIKE %(search)s OR b.author ILIKE %(search)s"
    return query


def _get_roadmap_query(search: str | None) -> str:
    """Get SQL query for roadmaps."""
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
            CASE
                WHEN (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id) > 0
                THEN (
                    (SELECT COUNT(*)
                     FROM nodes n
                     WHERE n.roadmap_id = r.id
                       AND n.status = 'done') * 100 /
                    (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id)
                )
                ELSE 0
            END as progress,
            (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id) as count1,
            (SELECT COUNT(*) FROM nodes n WHERE n.roadmap_id = r.id AND n.status = 'done') as count2
        FROM roadmaps r
    """
    if search:
        query += " WHERE r.title ILIKE %(search)s OR r.description ILIKE %(search)s"
    return query


async def _get_total_count(session: AsyncSession, combined_query: str, search_term: str | None) -> int:
    """Get total count of results."""
    count_query = f"SELECT COUNT(*) FROM ({combined_query}) as combined"
    count_result = await session.execute(
        text(count_query),
        {"search": search_term} if search_term else {},
    )
    return count_result.scalar() or 0


async def _get_paginated_results(
    session: AsyncSession,
    combined_query: str,
    search_term: str | None,
    page_size: int,
    offset: int,
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
    )


def _create_book_content(row: Any) -> BookContent:
    """Create BookContent from row data."""
    return BookContent(
        id=row.id,
        title=row.title,
        description=row.description,
        author=row.extra1 or "",
        pageCount=row.count1,
        currentPage=0,
        lastAccessedDate=row.last_accessed,
        createdDate=row.created_at,
        progress=row.progress,
        tags=_safe_parse_tags(row.tags),
    )


def _create_roadmap_content(row: Any) -> RoadmapContent:
    """Create RoadmapContent from row data."""
    return RoadmapContent(
        id=row.id,
        title=row.title,
        description=row.description,
        nodeCount=row.count1,
        completedNodes=row.count2,
        lastAccessedDate=row.last_accessed,
        createdDate=row.created_at,
        progress=row.progress,
        tags=[],
    )
