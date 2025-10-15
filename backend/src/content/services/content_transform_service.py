"""Content transformation service."""

import json
import logging
from typing import Any

from src.content.schemas import (
    BookContent,
    ContentMetadata,
    CourseContent,
    ProgressData,
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


def _create_progress_data(percentage: float = 0, completed_items: int = 0, total_items: int = 0) -> ProgressData:
    """Create standardized progress data."""
    return ProgressData(percentage=percentage, completed_items=completed_items, total_items=total_items)


class ContentTransformService:
    """Service for transforming content data."""

    @staticmethod
    def transform_rows_to_items(rows: list[Any]) -> list[Any]:
        """Transform database rows to content items."""
        items: list[Any] = []
        for row in rows:
            if row.type == "youtube":
                items.append(ContentTransformService._create_youtube_content(row))
            elif row.type == "book":
                items.append(ContentTransformService._create_book_content(row))
            elif row.type == "course":
                items.append(ContentTransformService._create_course_content(row))
        return items

    @staticmethod
    def _create_youtube_content(row: Any) -> YoutubeContent:
        """Create YoutubeContent from row data."""
        # Extract video ID from extra2 if it's a YouTube URL/thumbnail
        video_id = None
        if row.extra2 and ("ytimg.com" in row.extra2 or "youtube.com" in row.extra2):
            # YouTube thumbnail URLs contain the video ID
            parts = row.extra2.split("/")
            for part in parts:
                if part and len(part) == 11:  # YouTube video IDs are 11 chars
                    video_id = part
                    break

        metadata = ContentMetadata(platform="youtube", video_id=video_id)

        # Progress will be calculated later by the progress service
        progress = _create_progress_data(percentage=row.progress or 0, completed_items=0, total_items=0)

        return YoutubeContent(
            id=row.id,
            title=row.title,
            description=row.description,
            channel=row.extra1 or "",
            length=row.count1,  # Duration in seconds
            thumbnail_url=row.extra2,
            created_at=row.created_at,
            updated_at=row.last_accessed or row.created_at,
            progress=progress,
            tags=_safe_parse_tags(row.tags),
            status="archived" if row.archived else "active",
            metadata=metadata,
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

        metadata = ContentMetadata(
            pages=row.count1,
            file_type="pdf",  # Default for now, could be extracted from file
        )

        # Progress will be calculated later by the progress service
        progress = _create_progress_data(percentage=row.progress or 0, completed_items=0, total_items=0)

        book_content = BookContent(
            id=row.id,
            title=row.title,
            description=row.description,
            author=row.extra1 or "",
            page_count=row.count1,
            current_page=row.count2 or 0,
            created_at=row.created_at,
            updated_at=row.last_accessed or row.created_at,
            progress=progress,
            tags=_safe_parse_tags(row.tags),
            status="archived" if row.archived else "active",
            toc_progress=toc_progress,
            metadata=metadata,
        )

        return book_content

    @staticmethod
    def _create_course_content(row: Any) -> CourseContent:
        """Create CourseContent from row data."""
        metadata = ContentMetadata(
            ai_generated=True,
            modules_count=row.count2 or 0,
        )

        # Progress will be calculated later by the progress service
        progress = _create_progress_data(
            percentage=row.progress or 0, completed_items=row.count2 or 0, total_items=row.count1 or 0
        )

        return CourseContent(
            id=row.id,
            title=row.title,
            description=row.description,
            lesson_count=row.count1 or 0,
            completed_lessons=row.count2 or 0,
            author="AI",  # Default for AI-generated courses
            created_at=row.created_at,
            updated_at=row.last_accessed or row.created_at,
            progress=progress,
            tags=_safe_parse_tags(row.tags),
            status="archived" if row.archived else "active",
            metadata=metadata,
        )
