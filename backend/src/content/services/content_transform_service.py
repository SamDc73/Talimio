"""Content transformation service."""

import json
import logging
import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from src.content.schemas import (
    BookContent,
    ContentMetadata,
    CourseContent,
    ProgressData,
    VideoContent,
)


logger = logging.getLogger(__name__)
_YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


def _is_valid_youtube_video_id(candidate: str) -> bool:
    return bool(_YOUTUBE_VIDEO_ID_PATTERN.fullmatch(candidate))


def _extract_youtube_video_id(raw_url: str | None) -> str | None:
    """Extract a YouTube video ID from trusted YouTube/ytimg hosts only."""
    if not raw_url:
        return None

    try:
        parsed_url = urlparse(raw_url)
    except ValueError:
        return None

    hostname = (parsed_url.hostname or "").lower()
    if not hostname:
        return None

    path_segments = [segment for segment in parsed_url.path.split("/") if segment]
    candidate: str | None = None

    if hostname in {"youtu.be", "www.youtu.be"} and path_segments:
        candidate = path_segments[0]
    elif hostname == "youtube.com" or hostname.endswith(".youtube.com"):
        if parsed_url.path == "/watch":
            candidate = parse_qs(parsed_url.query).get("v", [""])[0]
        elif len(path_segments) >= 2 and path_segments[0] in {"embed", "v", "shorts", "live"}:
            candidate = path_segments[1]
    elif (
        (hostname == "ytimg.com" or hostname.endswith(".ytimg.com"))
        and len(path_segments) >= 2
        and path_segments[0] in {"vi", "vi_webp", "an_webp"}
    ):
        candidate = path_segments[1]

    if candidate and _is_valid_youtube_video_id(candidate):
        return candidate
    return None


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
            if row.type == "video":
                items.append(ContentTransformService._create_video_content(row))
            elif row.type == "book":
                items.append(ContentTransformService._create_book_content(row))
            elif row.type == "course":
                items.append(ContentTransformService._create_course_content(row))
        return items

    @staticmethod
    def _create_video_content(row: Any) -> VideoContent:
        """Create VideoContent from row data."""
        video_id = _extract_youtube_video_id(row.extra2)

        metadata = ContentMetadata(platform="youtube", video_id=video_id)

        # Progress will be calculated later by the progress service
        progress = _create_progress_data(percentage=row.progress or 0, completed_items=0, total_items=0)

        return VideoContent(
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

        return BookContent(
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
