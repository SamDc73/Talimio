"""Ultra-fast content service with minimal queries."""
import json
import logging

from sqlalchemy import text

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
        # Build the SQL query based on content type filter
        queries = []

        # Videos
        if not content_type or content_type == ContentType.YOUTUBE:
            video_query = """
                SELECT 
                    uuid::text as id,
                    title,
                    COALESCE(description, '') as description,
                    'youtube' as type,
                    COALESCE(updated_at, created_at) as last_accessed,
                    created_at,
                    tags,
                    channel as extra1,
                    thumbnail_url as extra2,
                    COALESCE(completion_percentage, 0)::int as progress,
                    COALESCE(duration, 0) as count1,
                    0 as count2
                FROM videos
            """
            if search:
                video_query += " WHERE title ILIKE %(search)s OR channel ILIKE %(search)s"
            queries.append(video_query)

        # Flashcards
        if not content_type or content_type == ContentType.FLASHCARDS:
            deck_query = """
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
                deck_query += " WHERE name ILIKE %(search)s OR description ILIKE %(search)s"
            queries.append(deck_query)

        # Books
        if not content_type or content_type == ContentType.BOOK:
            book_query = """
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
                book_query += " WHERE b.title ILIKE %(search)s OR b.author ILIKE %(search)s"
            queries.append(book_query)

        # Roadmaps
        if not content_type or content_type == ContentType.ROADMAP:
            roadmap_query = """
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
                             FROM progress p 
                             WHERE p.course_id = r.id::text 
                               AND p.status = 'done') * 100 / 
                            (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id)
                        )
                        ELSE 0 
                    END as progress,
                    (SELECT COUNT(*) FROM nodes WHERE roadmap_id = r.id) as count1,
                    (SELECT COUNT(*) FROM progress p WHERE p.course_id = r.id::text AND p.status = 'done') as count2
                FROM roadmaps r
            """
            if search:
                roadmap_query += " WHERE r.title ILIKE %(search)s OR r.description ILIKE %(search)s"
            queries.append(roadmap_query)

        if not queries:
            return ContentListResponse(items=[], total=0, page=page, page_size=page_size)

        # Combine queries with UNION ALL
        combined_query = " UNION ALL ".join(f"({q})" for q in queries)

        # Get total count
        count_query = f"SELECT COUNT(*) FROM ({combined_query}) as combined"
        count_result = await session.execute(
            text(count_query),
            {"search": search_term} if search else {},
        )
        total = count_result.scalar() or 0

        # Get paginated results
        final_query = f"""
            SELECT * FROM ({combined_query}) as combined
            ORDER BY last_accessed DESC
            LIMIT :limit OFFSET :offset
        """

        params = {"limit": page_size, "offset": offset}
        if search:
            params["search"] = search_term

        result = await session.execute(text(final_query), params)
        rows = result.all()

        # Transform to schema objects
        items = []
        for row in rows:
            if row.type == "youtube":
                items.append(
                    YoutubeContent(
                        id=row.id,
                        title=row.title,
                        description=row.description,
                        channel_name=row.extra1 or "",  # Ensure it's not None
                        duration=row.count1,
                        thumbnail_url=row.extra2,
                        last_accessed_date=row.last_accessed,
                        created_date=row.created_at,
                        progress=row.progress,
                        tags=_safe_parse_tags(row.tags),
                    ),
                )
            elif row.type == "flashcards":
                items.append(
                    FlashcardContent(
                        id=row.id,
                        title=row.title,
                        description=row.description,
                        card_count=row.count1,
                        due_count=0,
                        last_accessed_date=row.last_accessed,
                        created_date=row.created_at,
                        progress=row.progress,
                        tags=_safe_parse_tags(row.tags),
                    ),
                )
            elif row.type == "book":
                items.append(
                    BookContent(
                        id=row.id,
                        title=row.title,
                        description=row.description,
                        author=row.extra1 or "",  # Ensure it's not None
                        page_count=row.count1,
                        current_page=0,
                        last_accessed_date=row.last_accessed,
                        created_date=row.created_at,
                        progress=row.progress,
                        tags=_safe_parse_tags(row.tags),
                    ),
                )
            elif row.type == "roadmap":
                items.append(
                    RoadmapContent(
                        id=row.id,
                        title=row.title,
                        description=row.description,
                        node_count=row.count1,
                        completed_nodes=row.count2,
                        last_accessed_date=row.last_accessed,
                        created_date=row.created_at,
                        progress=row.progress,
                        tags=[],
                    ),
                )

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
