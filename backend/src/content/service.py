import json
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Select, or_, select
from sqlalchemy.orm import selectinload

from src.books.models import Book
from src.content.schemas import (
    BookContent,
    ContentListResponse,
    ContentType,
    FlashcardContent,
    RoadmapContent,
    YoutubeContent,
)
from src.database.session import async_session_maker
from src.flashcards.models import FlashcardDeck
from src.roadmaps.models import Roadmap
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
    """Fetch YouTube videos from the database."""
    items = []
    try:
        async with async_session_maker() as session:
            video_stmt = select(Video)
            video_stmt = apply_search_filter(video_stmt, Video, ["title", "channel"], search)
            result = await session.execute(video_stmt)
            videos = result.scalars().all()

            items.extend(
                YoutubeContent(
                    id=str(video.id),
                    title=video.title,
                    description=video.description or "",
                    channel_name=video.channel,
                    duration=video.duration,
                    thumbnail_url=video.thumbnail_url,
                    last_accessed_date=video.updated_at or video.created_at,
                    created_date=video.created_at,
                    progress=video.completion_percentage or 0,
                    tags=video.tags.split(",") if video.tags else [],
                )
                for video in videos
            )
    except Exception as e:
        # Log the error but continue with other content types
        logger.warning(f"Failed to fetch YouTube videos: {e}")

    return items


async def fetch_flashcard_decks(search: str | None = None) -> list[FlashcardContent]:
    """Fetch flashcard decks from the database."""
    items = []
    try:
        async with async_session_maker() as session:
            deck_stmt = select(FlashcardDeck).options(selectinload(FlashcardDeck.cards))
            deck_stmt = apply_search_filter(deck_stmt, FlashcardDeck, ["name", "description"], search)
            result = await session.execute(deck_stmt)
            decks = result.scalars().all()

            for deck in decks:
                # Count total cards and due cards
                card_count = len(deck.cards) if deck.cards else 0
                due_count = (
                    sum(1 for card in deck.cards if card.due and card.due <= datetime.now(UTC)) if deck.cards else 0
                )

                items.append(
                    FlashcardContent(
                        id=str(deck.id),
                        title=deck.name,
                        description=deck.description or "",
                        card_count=card_count,
                        due_count=due_count,
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
    """Fetch books from the database."""
    items = []
    try:
        async with async_session_maker() as session:
            book_stmt = select(Book).options(selectinload(Book.progress_records))
            book_stmt = apply_search_filter(book_stmt, Book, ["title", "author"], search)
            result = await session.execute(book_stmt)
            books = result.scalars().all()

            for book in books:
                # Get the latest progress record
                progress_record = None
                if book.progress_records:
                    progress_record = max(book.progress_records, key=lambda p: p.updated_at)

                current_page = progress_record.current_page if progress_record else 0
                progress = progress_record.progress_percentage if progress_record else 0
                last_read_at = progress_record.last_read_at if progress_record else None

                items.append(
                    BookContent(
                        id=str(book.id),
                        title=book.title,
                        description=book.description or "",
                        author=book.author,
                        page_count=book.total_pages,
                        current_page=current_page,
                        last_accessed_date=last_read_at or book.created_at,
                        created_date=book.created_at,
                        progress=progress,
                        tags=_safe_parse_tags(book.tags),
                    ),
                )
    except Exception as e:
        logger.warning(f"Failed to fetch books: {e}")

    return items


async def fetch_roadmaps(search: str | None = None) -> list[RoadmapContent]:
    """Fetch roadmaps from the database."""
    items = []
    try:
        async with async_session_maker() as session:
            roadmap_stmt = select(Roadmap).options(selectinload(Roadmap.nodes))
            roadmap_stmt = apply_search_filter(roadmap_stmt, Roadmap, ["title", "description"], search)
            result = await session.execute(roadmap_stmt)
            roadmaps = result.scalars().all()

            for roadmap in roadmaps:
                # Count nodes
                node_count = len(roadmap.nodes) if roadmap.nodes else 0

                # For now, use node status to calculate progress
                completed_count = sum(1 for node in roadmap.nodes if node.status == "completed") if roadmap.nodes else 0

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
