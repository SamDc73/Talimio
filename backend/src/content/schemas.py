from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Enumeration of content types available in the learning platform."""

    YOUTUBE = "youtube"
    FLASHCARDS = "flashcards"
    BOOK = "book"
    COURSE = "course"


class ProgressData(BaseModel):
    """Standardized progress data structure."""

    percentage: float = Field(ge=0, le=100)
    completed_items: int = Field(ge=0)
    total_items: int = Field(ge=0)

    model_config = {"populate_by_name": True}


class ContentMetadata(BaseModel):
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

    model_config = {"extra": "allow", "populate_by_name": True}


class ContentItemBase(BaseModel):
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
    tags: list[str] = []
    status: str = "active"  # active|archived|draft
    estimated_time: int | None = None  # in minutes

    # Type-specific fields at root level
    author: str | None = None  # Books & Courses only
    channel: str | None = None  # Videos only
    length: int | None = None  # Videos only (seconds)

    # Type-specific metadata
    metadata: ContentMetadata = Field(default_factory=ContentMetadata)

    model_config = {"populate_by_name": True}


class YoutubeContent(ContentItemBase):
    """Model for YouTube video content items."""

    type: ContentType = ContentType.YOUTUBE
    channel: str  # Required for videos
    length: int | None = None  # Duration in seconds
    thumbnail_url: str | None = None

    model_config = {"populate_by_name": True}


class FlashcardContent(ContentItemBase):
    """Model for flashcard deck content items."""

    type: ContentType = ContentType.FLASHCARDS
    card_count: int = 0
    due_count: int = 0

    model_config = {"populate_by_name": True}


class BookContent(ContentItemBase):
    """Model for book content items."""

    type: ContentType = ContentType.BOOK
    author: str  # Required for books
    page_count: int | None = None
    current_page: int = 0
    toc_progress: dict[str, Any] | None = None  # Internal use

    model_config = {"populate_by_name": True}


class CourseContent(ContentItemBase):
    """Model for course content items."""

    type: ContentType = ContentType.COURSE
    author: str = "AI"  # Default to AI for now
    lesson_count: int = 0
    completed_lessons: int = 0

    model_config = {"populate_by_name": True}


class ContentListResponse(BaseModel):
    """Response model for paginated content list."""

    items: list[YoutubeContent | FlashcardContent | BookContent | CourseContent]
    total: int
    page: int
    per_page: int  # Changed from page_size to match spec

    model_config = {"populate_by_name": True}
