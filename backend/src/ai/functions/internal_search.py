"""Internal library search functionality.

This module handles searching the platform's own database for existing
courses, lessons, books, and videos that match the user's learning needs.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from src.books.models import Book
from src.courses.models import Roadmap
from src.database.session import async_session_maker
from src.videos.models import Video

from .registry import register_function


logger = logging.getLogger(__name__)


async def _search_roadmaps(session: Any, topic: str, user_id: UUID | None = None) -> list[dict[str, Any]]:
    """Search for roadmaps/courses in the database."""
    roadmap_query = select(Roadmap).options(selectinload(Roadmap.nodes))

    # Build search conditions
    search_conditions = [Roadmap.title.ilike(f"%{topic}%"), Roadmap.description.ilike(f"%{topic}%")]

    if user_id:
        search_conditions.append(Roadmap.user_id == user_id)

    roadmap_query = roadmap_query.where(or_(*search_conditions))
    roadmap_result = await session.execute(roadmap_query)
    roadmaps = roadmap_result.scalars().all()

    return [
        {
            "id": str(roadmap.id),
            "title": roadmap.title,
            "description": roadmap.description,
            "created_at": roadmap.created_at.isoformat() if roadmap.created_at else None,
            "node_count": len(roadmap.nodes) if roadmap.nodes else 0,
            "type": "course",
        }
        for roadmap in roadmaps
    ]


async def _search_books(session: Any, topic: str, user_id: UUID | None = None) -> list[dict[str, Any]]:
    """Search for books in the database."""
    book_query = select(Book)

    search_conditions = [Book.title.ilike(f"%{topic}%"), Book.author.ilike(f"%{topic}%")]

    if user_id:
        search_conditions.append(Book.user_id == user_id)

    book_query = book_query.where(or_(*search_conditions))
    book_result = await session.execute(book_query)
    books = book_result.scalars().all()

    return [
        {
            "id": str(book.id),
            "title": book.title,
            "author": book.author,
            "description": book.description or "",
            "file_size": book.file_size,
            "total_pages": book.total_pages,
            "current_page": book.current_page,
            "type": "book",
        }
        for book in books
    ]


async def _search_videos(session: Any, topic: str, user_id: UUID | None = None) -> list[dict[str, Any]]:
    """Search for videos in the database."""
    video_query = select(Video)

    search_conditions = [
        Video.title.ilike(f"%{topic}%"),
        Video.description.ilike(f"%{topic}%"),
    ]

    if user_id:
        search_conditions.append(Video.user_id == user_id)

    video_query = video_query.where(or_(*search_conditions))
    video_result = await session.execute(video_query)
    videos = video_result.scalars().all()

    return [
        {
            "id": str(video.id),
            "title": video.title,
            "description": video.description or "",
            "channel_name": video.channel_id if hasattr(video, "channel_id") else "",
            "duration": video.duration,
            "url": video.url,
            "type": "video",
        }
        for video in videos
    ]


@register_function(
    {
        "type": "function",
        "name": "search_internal_library",
        "description": "Search our platform's library for existing courses, lessons, books, and videos",
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to search for"},
                "content_type": {"type": "string", "enum": ["all", "course", "book", "video"]},
                "user_id": {"type": ["string", "null"], "description": "Filter by user's content"},
            },
            "required": ["topic"],
            "additionalProperties": False,
        },
        "strict": True,
    }
)
async def search_internal_library(topic: str, content_type: str = "all", user_id: UUID | None = None) -> dict[str, Any]:
    """Search platform's internal library for existing content.

    Args:
        topic: Topic to search for
        content_type: Type of content to search for (all, course, book, video)
        user_id: Optional user ID to filter content

    Returns
    -------
        Dictionary with search results from internal library
    """
    try:
        logger.info("Searching internal library for topic: %s, type: %s, user_id: %s", topic, content_type, user_id)

        results = {"courses": [], "books": [], "videos": [], "total_found": 0}

        async with async_session_maker() as session:
            # Search roadmaps (courses)
            if content_type in ["all", "course"]:
                results["courses"] = await _search_roadmaps(session, topic, user_id)

            # Search books
            if content_type in ["all", "book"]:
                results["books"] = await _search_books(session, topic, user_id)

            # Search videos
            if content_type in ["all", "video"]:
                results["videos"] = await _search_videos(session, topic, user_id)

        results["total_found"] = len(results["courses"]) + len(results["books"]) + len(results["videos"])

        logger.info("Found %d items in internal library for topic: %s", results["total_found"], topic)
        return results

    except Exception as e:
        logger.exception("Error searching internal library")
        return {
            "error": f"Failed to search internal library: {e!s}",
            "courses": [],
            "books": [],
            "videos": [],
            "total_found": 0,
        }
