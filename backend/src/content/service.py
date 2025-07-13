"""Ultra-fast content service with minimal queries."""

import json
import logging
from datetime import UTC, datetime
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

    async with async_session_maker() as session:
        logger.info(
            f"🔍 list_content_fast called with include_archived={include_archived}, search={search}, content_type={content_type}"
        )

        queries = _build_content_queries(content_type, search, include_archived)

        if not queries:
            return ContentListResponse(items=[], total=0, page=page, page_size=page_size)

        combined_query = " UNION ALL ".join(f"({q})" for q in queries)
        total = await _get_total_count(session, combined_query, search_term)
        rows = await _get_paginated_results(session, combined_query, search_term, page_size, offset)
        items = _transform_rows_to_items(rows)

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


def _build_content_queries(
    content_type: ContentType | None, search: str | None, include_archived: bool = False
) -> list[str]:
    """Build SQL queries for different content types."""
    queries = []

    if not content_type or content_type == ContentType.YOUTUBE:
        queries.append(_get_video_query(search, include_archived))

    if not content_type or content_type == ContentType.FLASHCARDS:
        queries.append(_get_flashcard_query(search, include_archived))

    if not content_type or content_type == ContentType.BOOK:
        queries.append(_get_book_query(search, include_archived))

    if not content_type or content_type in (ContentType.ROADMAP, ContentType.COURSE):
        queries.append(_get_roadmap_query(search, include_archived))

    return queries


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
            COALESCE(v.archived, false) as archived
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

    # Build WHERE clause
    where_conditions = []
    if archived_only:
        where_conditions.append("v.archived = true")
    elif not include_archived:
        where_conditions.append("(v.archived = false OR v.archived IS NULL)")
    # If include_archived is True, don't add any archive filter (show all)

    if search:
        where_conditions.append("(v.title ILIKE %(search)s OR v.channel ILIKE %(search)s)")

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
            COALESCE(archived, false) as archived
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
        where_conditions.append("(name ILIKE %(search)s OR description ILIKE %(search)s)")

    if where_conditions:
        query += " WHERE " + " AND ".join(where_conditions)

    return query


def _get_book_query(search: str | None, include_archived: bool = False) -> str:
    """Get SQL query for books."""
    return _get_books_query(search, archived_only=False, include_archived=include_archived)


def _get_books_query(search: str | None, archived_only: bool = False, include_archived: bool = False) -> str:
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
            COALESCE(
                (SELECT current_page
                 FROM book_progress
                 WHERE book_id = b.id
                 ORDER BY updated_at DESC
                 LIMIT 1), 1
            ) as count2,
            COALESCE(b.archived, false) as archived
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
        where_conditions.append("(b.title ILIKE %(search)s OR b.author ILIKE %(search)s)")

    if where_conditions:
        query += " WHERE " + " AND ".join(where_conditions)

    return query


def _get_roadmap_query(search: str | None, include_archived: bool = False) -> str:
    """Get SQL query for roadmaps."""
    return _get_roadmaps_query(search, archived_only=False, include_archived=include_archived)


def _get_roadmaps_query(search: str | None, archived_only: bool = False, include_archived: bool = False) -> str:
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
            (SELECT COUNT(*) FROM nodes n WHERE n.roadmap_id = r.id AND n.status = 'done') as count2,
            COALESCE(r.archived, false) as archived
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
        where_conditions.append("(r.title ILIKE %(search)s OR r.description ILIKE %(search)s)")

    if where_conditions:
        query += " WHERE " + " AND ".join(where_conditions)

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
) -> ContentListResponse:
    """
    List only archived content across different types.

    Similar to list_content_fast but filters for archived = true.
    """
    offset = (page - 1) * page_size
    search_term = f"%{search}%" if search else None

    # Construct the combined query with archived filter
    if content_type:
        if content_type == ContentType.YOUTUBE:
            combined_query = _get_youtube_query(search, archived_only=True)
        elif content_type == ContentType.FLASHCARDS:
            combined_query = _get_flashcards_query(search, archived_only=True)
        elif content_type == ContentType.BOOK:
            combined_query = _get_books_query(search, archived_only=True)
        elif content_type == ContentType.ROADMAP:
            combined_query = _get_roadmaps_query(search, archived_only=True)
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
            {_get_roadmaps_query(search, archived_only=True)}
        """

    async with async_session_maker() as session:
        # Get total count and paginated results
        total = await _get_total_count(session, combined_query, search_term)
        rows = await _get_paginated_results(session, combined_query, search_term, page_size, offset)

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
                {"roadmap_id": uuid_id}
            )

            # Now delete the roadmap itself
            await session.execute(
                text("DELETE FROM roadmaps WHERE id = :roadmap_id"),
                {"roadmap_id": uuid_id}
            )
        else:
            # Delete using ORM to ensure proper cascade deletion for other content types
            await session.delete(content_obj)

        await session.commit()
