"""Content transformation service."""

import json
import logging
from typing import Any

from src.content.schemas import (
    BookContent,
    CourseContent,
    FlashcardContent,
    YoutubeContent,
)


logger = logging.getLogger(__name__)


def _safe_parse_tags(tags_json: str | None) -> list[str]:
    """Safely parse tags from JSON string."""
    if not tags_json:
        return []
    try:
        return json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []


class ContentTransformService:
    """Service for transforming content data."""

    @staticmethod
    def transform_rows_to_items(rows: list[Any]) -> list[Any]:
        """Transform database rows to content items."""
        items: list[Any] = []
        for row in rows:
            if row.type == "youtube":
                items.append(ContentTransformService._create_youtube_content(row))
            elif row.type == "flashcards":
                items.append(ContentTransformService._create_flashcard_content(row))
            elif row.type == "book":
                items.append(ContentTransformService._create_book_content(row))
            elif row.type == "roadmap":
                items.append(ContentTransformService._create_roadmap_content(row))
        return items

    @staticmethod
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

    @staticmethod
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

    @staticmethod
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

    @staticmethod
    def _create_roadmap_content(row: Any) -> CourseContent:
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
