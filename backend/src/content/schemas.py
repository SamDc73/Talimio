from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Enumeration of content types available in the learning platform."""

    YOUTUBE = "youtube"
    FLASHCARDS = "flashcards"
    BOOK = "book"
    ROADMAP = "roadmap"
    COURSE = "course"  # Alias for roadmap to support frontend course terminology


class ContentItemBase(BaseModel):
    """Base model for all content items with common fields."""

    id: str
    type: ContentType
    title: str
    description: str
    last_accessed_date: datetime = Field(alias="lastAccessedDate")
    created_date: datetime = Field(alias="createdDate")
    progress: float = Field(ge=0, le=100)
    tags: list[str] = []
    archived: bool = False

    model_config = {"populate_by_name": True}


class YoutubeContent(ContentItemBase):
    """Model for YouTube video content items."""

    type: ContentType = ContentType.YOUTUBE
    channel_name: str = Field(alias="channelName")
    duration: int | None = None
    thumbnail_url: str | None = Field(None, alias="thumbnailUrl")

    model_config = {"populate_by_name": True}


class FlashcardContent(ContentItemBase):
    """Model for flashcard deck content items."""

    type: ContentType = ContentType.FLASHCARDS
    card_count: int = Field(alias="cardCount")
    due_count: int = Field(0, alias="dueCount")

    model_config = {"populate_by_name": True}


class BookContent(ContentItemBase):
    """Model for book content items."""

    type: ContentType = ContentType.BOOK
    author: str
    page_count: int | None = Field(None, alias="pageCount")
    current_page: int | None = Field(0, alias="currentPage")

    model_config = {"populate_by_name": True}


class RoadmapContent(ContentItemBase):
    """Model for roadmap content items."""

    type: ContentType = ContentType.ROADMAP
    node_count: int = Field(alias="nodeCount")
    completed_nodes: int = Field(0, alias="completedNodes")

    model_config = {"populate_by_name": True}


class CourseContent(ContentItemBase):
    """Model for course content items (alias for roadmap)."""

    type: ContentType = ContentType.COURSE
    node_count: int = Field(alias="nodeCount")
    completed_nodes: int = Field(0, alias="completedNodes")

    model_config = {"populate_by_name": True}


class ContentListResponse(BaseModel):
    """Response model for paginated content list."""

    items: list[YoutubeContent | FlashcardContent | BookContent | RoadmapContent | CourseContent]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    model_config = {"populate_by_name": True}
