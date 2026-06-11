from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue

from src.config.schema_casing import CamelModel


class ContentType(StrEnum):
    """Enumeration of content types available in the learning platform."""

    VIDEO = "video"
    YOUTUBE = "youtube"
    BOOK = "book"
    COURSE = "course"


def normalize_content_type(content_type: ContentType) -> ContentType:
    """Normalize accepted aliases to canonical content types."""
    if content_type == ContentType.YOUTUBE:
        return ContentType.VIDEO
    return content_type


ContentItemStatus = Literal["active", "archived"]
ContentStatusFilter = Literal["active", "archived", "all"]

# Canonical generation/processing lifecycle shared across content types.
# Mapped from course.generation_status and book/video rag_status so the client
# can tell a failed or still-building item apart from a ready one.
ContentProcessingStatus = Literal["ready", "processing", "failed"]


class ProgressData(CamelModel):
    """Standardized progress data structure."""

    percentage: float = Field(ge=0, le=100)
    completed_items: int = Field(ge=0)
    total_items: int = Field(ge=0)


class ContentMetadata(CamelModel):
    """Type-specific metadata container."""

    # Course-specific
    ai_generated: bool | None = None
    modules_count: int | None = None

    # Video-specific
    platform: str | None = None
    video_id: str | None = None

    # Book-specific
    pages: int | None = None
    file_type: str | None = None

    model_config = ConfigDict(extra="allow")


class ContentItemBase(CamelModel):
    """Base model for all content items with common fields."""

    # Core fields (REQUIRED for all types)
    id: str
    type: ContentType
    title: str
    description: str
    progress: ProgressData
    created_at: datetime
    updated_at: datetime

    # Common optional fields
    tags: list[str] = Field(default_factory=list)
    status: ContentItemStatus = "active"
    processing_status: ContentProcessingStatus = "ready"
    estimated_time: int | None = None  # in minutes

    # Type-specific fields at root level
    author: str | None = None  # Books & Courses only
    channel: str | None = None  # Videos only
    length: int | None = None  # Videos only (seconds)

    # Type-specific metadata
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)


class VideoContent(ContentItemBase):
    """Model for video content items."""

    type: ContentType = ContentType.VIDEO
    channel: str  # Required for videos
    length: int | None = None  # Duration in seconds
    thumbnail_url: str | None = None


class BookContent(ContentItemBase):
    """Model for book content items."""

    type: ContentType = ContentType.BOOK
    author: str  # Required for books
    page_count: int | None = None
    current_page: int = 0
    toc_progress: dict[str, JsonValue] | None = None  # Internal use


class CourseContent(ContentItemBase):
    """Model for course content items."""

    type: ContentType = ContentType.COURSE
    author: str = "AI"  # Default to AI for now
    lesson_count: int = 0
    completed_lessons: int = 0


class ContentListResponse(CamelModel):
    """Response model for paginated content list."""

    items: list[VideoContent | BookContent | CourseContent]
    total: int
    page: int
    per_page: int  # Changed from page_size to match spec
