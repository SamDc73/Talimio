"""Content transformation service."""

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Protocol
from urllib.parse import parse_qs, urlparse

from pydantic import JsonValue

from src.content.schemas import (
    BookContent,
    ContentMetadata,
    CourseContent,
    ProgressData,
    VideoContent,
)


logger = logging.getLogger(__name__)
_YOUTUBE_VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class ContentProjectionRow(Protocol):
    """Projected content row returned by the unified content list query."""

    id: uuid.UUID
    type: str
    title: str
    description: str
    extra1: str | None
    extra2: str | None
    count1: int | None
    count2: int | None
    count3: int | None
    progress: float | None
    created_at: datetime
    last_accessed: datetime | None
    tags: str | None
    archived: bool
    toc_progress: str | None


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
        parsed = json.loads(tags_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [tag for tag in parsed if isinstance(tag, str)]


def _safe_parse_json_object(raw_json: str) -> dict[str, JsonValue]:
    """Parse a JSON object, dropping malformed or non-object payloads."""
    try:
        parsed = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    if not isinstance(parsed, dict):
        return {}
    return {key: value for key, value in parsed.items() if isinstance(key, str)}


def _create_progress_data(percentage: float = 0, completed_items: int = 0, total_items: int = 0) -> ProgressData:
    """Create standardized progress data."""
    return ProgressData(percentage=percentage, completed_items=completed_items, total_items=total_items)


class ContentTransformService:
    """Service for transforming content data."""

    @staticmethod
    def transform_rows_to_items(rows: list[ContentProjectionRow]) -> list[VideoContent | BookContent | CourseContent]:
        """Transform database rows to content items."""
        items: list[VideoContent | BookContent | CourseContent] = []
        for row in rows:
            if row.type == "video":
                items.append(ContentTransformService._create_video_content(row))
            elif row.type == "book":
                items.append(ContentTransformService._create_book_content(row))
            elif row.type == "course":
                items.append(ContentTransformService._create_course_content(row))
        return items

    @staticmethod
    def _create_video_content(row: ContentProjectionRow) -> VideoContent:
        """Create VideoContent from row data."""
        video_id = _extract_youtube_video_id(row.extra2)

        metadata = ContentMetadata(platform="youtube", video_id=video_id)

        progress = _create_progress_data(percentage=row.progress or 0, completed_items=0, total_items=0)

        return VideoContent(
            id=str(row.id),
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
    def _create_book_content(row: ContentProjectionRow) -> BookContent:
        """Create BookContent from row data."""
        # Parse toc_progress from JSON string
        toc_progress = _safe_parse_json_object(row.toc_progress) if row.toc_progress else None

        metadata = ContentMetadata(
            pages=row.count1,
            file_type="pdf",  # Default for now, could be extracted from file
        )

        progress = _create_progress_data(percentage=row.progress or 0, completed_items=0, total_items=0)

        return BookContent(
            id=str(row.id),
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
    def _create_course_content(row: ContentProjectionRow) -> CourseContent:
        """Create CourseContent from row data."""
        completed_lesson_count = row.count3 or 0
        metadata = ContentMetadata(
            ai_generated=True,
            modules_count=row.count2 or 0,
        )

        progress = _create_progress_data(
            percentage=row.progress or 0, completed_items=completed_lesson_count, total_items=row.count1 or 0
        )

        return CourseContent(
            id=str(row.id),
            title=row.title,
            description=row.description,
            lesson_count=row.count1 or 0,
            completed_lessons=completed_lesson_count,
            author="AI",  # Default for AI-generated courses
            created_at=row.created_at,
            updated_at=row.last_accessed or row.created_at,
            progress=progress,
            tags=_safe_parse_tags(row.tags),
            status="archived" if row.archived else "active",
            metadata=metadata,
        )
