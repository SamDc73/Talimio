from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Enumeration of content types available in the learning platform."""

    YOUTUBE = "youtube"
    FLASHCARDS = "flashcards"
    BOOK = "book"
    ROADMAP = "roadmap"


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

    class Config:
        """Pydantic configuration for ContentItemBase."""

        populate_by_name = True


class YoutubeContent(ContentItemBase):
    """Model for YouTube video content items."""

    type: ContentType = ContentType.YOUTUBE
    channel_name: str = Field(alias="channelName")
    duration: int | None = None
    thumbnail_url: str | None = Field(None, alias="thumbnailUrl")

    class Config:
        """Pydantic configuration for YoutubeContent."""

        populate_by_name = True


class FlashcardContent(ContentItemBase):
    """Model for flashcard deck content items."""

    type: ContentType = ContentType.FLASHCARDS
    card_count: int = Field(alias="cardCount")
    due_count: int = Field(0, alias="dueCount")

    class Config:
        """Pydantic configuration for FlashcardContent."""

        populate_by_name = True


class BookContent(ContentItemBase):
    """Model for book content items."""

    type: ContentType = ContentType.BOOK
    author: str
    page_count: int | None = Field(None, alias="pageCount")
    current_page: int | None = Field(0, alias="currentPage")

    class Config:
        """Pydantic configuration for BookContent."""

        populate_by_name = True


class RoadmapContent(ContentItemBase):
    """Model for roadmap content items."""

    type: ContentType = ContentType.ROADMAP
    node_count: int = Field(alias="nodeCount")
    completed_nodes: int = Field(0, alias="completedNodes")

    class Config:
        """Pydantic configuration for RoadmapContent."""

        populate_by_name = True


class ContentListResponse(BaseModel):
    """Response model for paginated content list."""

    items: list[YoutubeContent | FlashcardContent | BookContent | RoadmapContent]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")

    class Config:
        """Pydantic configuration for ContentListResponse."""

        populate_by_name = True
