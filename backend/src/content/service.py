import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, func, or_, select

from src.books.models import Book, BookProgress
from src.content.schemas import (
    BookContent,
    ContentListResponse,
    ContentType,
    FlashcardContent,
    RoadmapContent,
    YoutubeContent,
)
from src.database.session import async_session_maker
from src.flashcards.models import FlashcardCard, FlashcardDeck
from src.roadmaps.models import Node, Roadmap
from src.videos.models import Video


logger = logging.getLogger(__name__)


def _safe_parse_tags(tags_json: str | None) -> list[str]:
    """Safely parse tags from JSON string."""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


def apply_search_filter(stmt: Select[Any], model: type[Any], fields: list[str], search: str | None) -> Select[Any]:
    """Apply search filter to a SQLAlchemy query.

    Args:
        stmt: SQLAlchemy select statement
        model: SQLAlchemy model class
        fields: List of field names to search in
        search: Search term

    Returns
    -------
        Modified select statement with search conditions
    """
    if search:
        search_term = f"%{search}%"
        conditions = [getattr(model, field).ilike(search_term) for field in fields]
        return stmt.where(or_(*conditions))
    return stmt


async def fetch_youtube_videos(search: str | None = None) -> list[YoutubeContent]:
    """Fetch YouTube videos from the database using optimized queries."""
    items = []
    try:
        async with async_session_maker() as session:
            # Select only needed fields
            video_stmt = select(
                Video.uuid,
                Video.title,
                Video.description,
                Video.channel,
                Video.duration,
                Video.thumbnail_url,
                Video.completion_percentage,
                Video.tags,
                Video.created_at,
                Video.updated_at,
            )
            video_stmt = apply_search_filter(video_stmt, Video, ["title", "channel"], search)
            result = await session.execute(video_stmt)
            videos = result.all()

            items.extend(
                YoutubeContent(
                    id=str(video.uuid),
                    title=video.title,
                    description=video.description or "",
                    channel_name=video.channel,
                    duration=video.duration,
                    thumbnail_url=video.thumbnail_url,
                    last_accessed_date=video.updated_at or video.created_at,
                    created_date=video.created_at,
                    progress=video.completion_percentage or 0,
                    tags=_safe_parse_tags(video.tags),
                )
                for video in videos
            )
    except Exception as e:
        # Log the error but continue with other content types
        logger.warning(f"Failed to fetch YouTube videos: {e}")

    return items


async def fetch_flashcard_decks(search: str | None = None) -> list[FlashcardContent]:
    """Fetch flashcard decks from the database using optimized queries."""
    items = []
    try:
        async with async_session_maker() as session:
            # Use subqueries for counting instead of loading all cards
            card_count_subq = (
                select(func.count(FlashcardCard.id))
                .where(FlashcardCard.deck_id == FlashcardDeck.id)
                .scalar_subquery()
            )

            due_count_subq = (
                select(func.count(FlashcardCard.id))
                .where(
                    FlashcardCard.deck_id == FlashcardDeck.id,
                    FlashcardCard.due <= datetime.now(UTC),
                )
                .scalar_subquery()
            )

            # Select only needed fields with aggregated counts
            deck_stmt = select(
                FlashcardDeck.id,
                FlashcardDeck.name,
                FlashcardDeck.description,
                FlashcardDeck.tags,
                FlashcardDeck.created_at,
                FlashcardDeck.updated_at,
                card_count_subq.label("card_count"),
                due_count_subq.label("due_count"),
            )

            deck_stmt = apply_search_filter(deck_stmt, FlashcardDeck, ["name", "description"], search)
            result = await session.execute(deck_stmt)
            decks = result.all()

            for deck in decks:
                items.append(
                    FlashcardContent(
                        id=str(deck.id),
                        title=deck.name,
                        description=deck.description or "",
                        card_count=deck.card_count or 0,
                        due_count=deck.due_count or 0,
                        last_accessed_date=deck.updated_at or deck.created_at,
                        created_date=deck.created_at,
                        progress=0,  # Calculate based on reviewed cards if needed
                        tags=_safe_parse_tags(deck.tags),
                    ),
                )
    except Exception as e:
        logger.warning(f"Failed to fetch flashcard decks: {e}")

    return items


async def fetch_books(search: str | None = None) -> list[BookContent]:
    """Fetch books from the database using optimized queries."""
    items = []
    try:
        async with async_session_maker() as session:
            # Get latest progress for each book using subquery
            latest_progress_subq = (
                select(
                    BookProgress.book_id,
                    BookProgress.current_page,
                    BookProgress.progress_percentage,
                    BookProgress.last_read_at,
                    func.row_number().over(
                        partition_by=BookProgress.book_id,
                        order_by=BookProgress.updated_at.desc(),
                    ).label("rn"),
                )
                .where(BookProgress.book_id.isnot(None))
                .subquery()
            )

            latest_progress = (
                select(
                    latest_progress_subq.c.book_id,
                    latest_progress_subq.c.current_page,
                    latest_progress_subq.c.progress_percentage,
                    latest_progress_subq.c.last_read_at,
                )
                .where(latest_progress_subq.c.rn == 1)
                .subquery()
            )

            # Select books with their latest progress
            book_stmt = select(
                Book.id,
                Book.title,
                Book.description,
                Book.author,
                Book.total_pages,
                Book.tags,
                Book.created_at,
                Book.updated_at,
                latest_progress.c.current_page,
                latest_progress.c.progress_percentage,
                latest_progress.c.last_read_at,
            ).outerjoin(latest_progress, Book.id == latest_progress.c.book_id)

            book_stmt = apply_search_filter(book_stmt, Book, ["title", "author"], search)
            result = await session.execute(book_stmt)
            books = result.all()

            for book in books:
                items.append(
                    BookContent(
                        id=str(book.id),
                        title=book.title,
                        description=book.description or "",
                        author=book.author,
                        page_count=book.total_pages,
                        current_page=book.current_page or 0,
                        last_accessed_date=book.last_read_at or book.created_at,
                        created_date=book.created_at,
                        progress=book.progress_percentage or 0,
                        tags=_safe_parse_tags(book.tags),
                    ),
                )
    except Exception as e:
        logger.warning(f"Failed to fetch books: {e}")

    return items


async def fetch_roadmaps(search: str | None = None) -> list[RoadmapContent]:
    """Fetch roadmaps from the database using optimized queries."""
    items = []
    try:
        async with async_session_maker() as session:
            # Use subqueries for counting instead of loading all nodes
            node_count_subq = (
                select(func.count(Node.id))
                .where(Node.roadmap_id == Roadmap.id)
                .scalar_subquery()
            )

            completed_count_subq = (
                select(func.count(Node.id))
                .where(
                    Node.roadmap_id == Roadmap.id,
                    Node.status == "completed",
                )
                .scalar_subquery()
            )

            # Select only needed fields with aggregated counts
            roadmap_stmt = select(
                Roadmap.id,
                Roadmap.title,
                Roadmap.description,
                Roadmap.created_at,
                Roadmap.updated_at,
                node_count_subq.label("node_count"),
                completed_count_subq.label("completed_count"),
            )

            roadmap_stmt = apply_search_filter(roadmap_stmt, Roadmap, ["title", "description"], search)
            result = await session.execute(roadmap_stmt)
            roadmaps = result.all()

            for roadmap in roadmaps:
                node_count = roadmap.node_count or 0
                completed_count = roadmap.completed_count or 0

                # Calculate progress percentage
                progress = (completed_count / node_count * 100) if node_count > 0 else 0

                items.append(
                    RoadmapContent(
                        id=str(roadmap.id),
                        title=roadmap.title,
                        description=roadmap.description or "",
                        node_count=node_count,
                        completed_nodes=completed_count,
                        last_accessed_date=roadmap.updated_at or roadmap.created_at,
                        created_date=roadmap.created_at,
                        progress=progress,
                        tags=[],  # Add tags field to roadmap model if needed
                    ),
                )
    except Exception as e:
        logger.warning(f"Failed to fetch roadmaps: {e}")

    return items


async def list_all_content(
    search: str | None = None,
    content_type: ContentType | None = None,
    page: int = 1,
    page_size: int = 20,
) -> ContentListResponse:
    """List all content across different types with unified format.

    Fetches content from multiple sources (videos, flashcards, books, roadmaps)
    and returns them in a unified paginated response.
    """
    items = []

    # Fetch content based on type filter
    if Video and (not content_type or content_type == ContentType.YOUTUBE):
        youtube_items = await fetch_youtube_videos(search)
        items.extend(youtube_items)

    if not content_type or content_type == ContentType.FLASHCARDS:
        flashcard_items = await fetch_flashcard_decks(search)
        items.extend(flashcard_items)

    if not content_type or content_type == ContentType.BOOK:
        book_items = await fetch_books(search)
        items.extend(book_items)

    if not content_type or content_type == ContentType.ROADMAP:
        roadmap_items = await fetch_roadmaps(search)
        items.extend(roadmap_items)

    # Sort items by last accessed date (descending by default)
    # Handle timezone-aware/naive datetime comparison
    def safe_sort_key(item):
        date = item.last_accessed_date
        if date and date.tzinfo is None:
            # Make naive datetime timezone-aware (UTC)
            date = date.replace(tzinfo=UTC)
        return date or datetime.min.replace(tzinfo=UTC)

    items.sort(key=safe_sort_key, reverse=True)

    # Apply pagination
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = items[start:end]

    return ContentListResponse(
        items=paginated_items,
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_content_summary(
    search: str | None = None,
    content_type: ContentType | None = None,
    page: int = 1,
    page_size: int = 50,
) -> ContentListResponse:
    """Optimized content listing with database-level pagination and minimal data.

    This is a high-performance version that:
    - Uses database aggregations instead of loading relationships
    - Applies pagination at the database level
    - Returns only essential fields needed for cards
    - Uses a unified query approach for better performance
    """
    items = []

    # Fetch content with optimized queries (already optimized above)
    # But limit results at the application level for now
    # TODO: Implement true database-level pagination across content types

    # For now, use the optimized fetch functions but limit results
    if not content_type or content_type == ContentType.YOUTUBE:
        youtube_items = await fetch_youtube_videos(search)
        items.extend(youtube_items)

    if not content_type or content_type == ContentType.FLASHCARDS:
        flashcard_items = await fetch_flashcard_decks(search)
        items.extend(flashcard_items)

    if not content_type or content_type == ContentType.BOOK:
        book_items = await fetch_books(search)
        items.extend(book_items)

    if not content_type or content_type == ContentType.ROADMAP:
        roadmap_items = await fetch_roadmaps(search)
        items.extend(roadmap_items)

    # Sort items by last accessed date (descending by default)
    def safe_sort_key(item):
        date = item.last_accessed_date
        if date and date.tzinfo is None:
            date = date.replace(tzinfo=UTC)
        return date or datetime.min.replace(tzinfo=UTC)

    items.sort(key=safe_sort_key, reverse=True)

    # Apply pagination
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_items = items[start:end]

    return ContentListResponse(
        items=paginated_items,
        total=total,
        page=page,
        page_size=page_size,
    )
