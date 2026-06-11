import uuid
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, field_validator

from src.config.schema_casing import CamelModel


BookRagStatus = Literal["pending", "processing", "completed", "failed"]
BookLearningStatus = Literal["not_started", "in_progress", "completed"]
BookFileType = Literal["pdf", "epub"]
MEDIA_TYPES: dict[BookFileType, str] = {"pdf": "application/pdf", "epub": "application/epub+zip"}


class BookCreate(CamelModel):
    """Schema for finalizing a direct upload into a book record."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    file_path: str
    storage_provider: str
    file_size: int | None = None
    author: str | None = Field(default=None, max_length=200)
    subtitle: str | None = Field(default=None, max_length=500)
    description: str | None = None
    isbn: str | None = Field(default=None, max_length=20)
    language: str | None = Field(default=None, max_length=10)
    publication_year: int | None = Field(default=None, ge=1000, le=2030)
    publisher: str | None = Field(default=None, max_length=200)
    tags: list[str] = Field(default_factory=list)
    process_in_background: bool = True


class BookUpdate(CamelModel):
    """Schema for updating a book."""

    title: str | None = Field(None, max_length=500)
    subtitle: str | None = Field(None, max_length=500)
    author: str | None = Field(None, max_length=200)
    description: str | None = None
    isbn: str | None = Field(None, max_length=20)
    language: str | None = Field(None, max_length=10)
    publication_year: int | None = Field(None, ge=1000, le=2030)
    publisher: str | None = Field(None, max_length=200)
    tags: list[str] | None = None
    table_of_contents: list[dict] | None = None


class TableOfContentsItem(CamelModel):
    """Schema for table of contents item."""

    id: str
    title: str
    page: int | None = None
    start_page: int | None = None
    end_page: int | None = None
    level: int = 0  # 0 for chapters, 1 for sections, etc.
    children: list[TableOfContentsItem] = Field(default_factory=list)


class BookTocChapterResponse(CamelModel):
    """Canonical chapter response for book table-of-contents endpoints."""

    id: str
    title: str
    page: int | None = None
    start_page: int | None = None
    end_page: int | None = None
    level: int = 0
    completed: bool = False
    children: list[BookTocChapterResponse] = Field(default_factory=list)


class BookResponse(CamelModel):
    """Schema for book response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    subtitle: str | None = None
    author: str
    description: str | None = None
    isbn: str | None = None
    language: str | None = None
    publication_year: int | None = None
    publisher: str | None = None
    tags: list[str] = Field(default_factory=list)
    file_type: BookFileType

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: str | list[str] | None) -> list[str]:
        """Convert tags from JSON string to list."""
        if v is None:
            return []
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        if isinstance(v, list):
            return v
        return []

    file_path: str
    storage_provider: str
    file_size: int
    total_pages: int | None = None
    table_of_contents: list[TableOfContentsItem] | None = None
    rag_status: BookRagStatus

    @field_validator("table_of_contents", mode="before")
    @classmethod
    def validate_table_of_contents(cls, v: str | list[dict] | None) -> list[dict] | None:
        """Convert table_of_contents from JSON string to list."""
        if v is None:
            return None
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return None
        if isinstance(v, list):
            return v
        return None

    rag_processed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class BookProgressBase(CamelModel):
    """Base schema for book progress."""

    current_page: int = Field(default=1, ge=1)
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    reading_time_minutes: int = Field(default=0, ge=0)
    status: BookLearningStatus = "not_started"
    notes: str | None = None
    bookmarks: list[int] = Field(default_factory=list)
    toc_progress: dict[str, bool] = Field(default_factory=dict)  # Maps section IDs to completion status


class BookProgressUpdate(CamelModel):
    """Schema for updating book progress."""

    current_page: int | None = Field(None, ge=1)
    total_pages: int | None = Field(None, ge=1)
    progress_percentage: float | None = Field(None, ge=0.0, le=100.0)
    reading_time_minutes: int | None = Field(None, ge=0)
    status: BookLearningStatus | None = None
    notes: str | None = None
    bookmarks: list[int] | None = None
    toc_progress: dict[str, bool] | None = None  # Maps section IDs to completion status


class BookProgressResponse(BookProgressBase):
    """Schema for book progress response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID | None = None  # Optional - might not exist for unsaved progress
    book_id: uuid.UUID
    total_pages_read: int
    last_read_at: datetime | None
    created_at: datetime | None = None  # None if not yet saved

    @field_validator("bookmarks", mode="before")
    @classmethod
    def validate_bookmarks(cls, v: str | list[int] | list[object] | None) -> list[int]:
        """Normalize bookmarks to a list of integers.

        Accepts:
        - JSON string representing a list
        - A list of ints/strings (strings will be coerced where possible)
        - None (returns empty list)
        """
        if v is None:
            return []
        # If provided as JSON string, parse first
        if isinstance(v, str):
            import json

            try:
                parsed = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
            v = parsed
        # Coerce any list-like into list[int]
        if isinstance(v, list):
            result: list[int] = []
            for item in v:
                try:
                    # Allow numeric strings to be coerced
                    if isinstance(item, str | int | float):
                        result.append(int(item))
                except (TypeError, ValueError):
                    # Skip non-coercible entries to maintain type safety
                    continue
            return result
        return []

    updated_at: datetime | None = None  # None if not yet saved

    @field_validator("toc_progress", mode="before")
    @classmethod
    def validate_toc_progress(cls, v: str | dict[str, bool] | None) -> dict[str, bool]:
        """Convert toc_progress from JSON string to dict."""
        if v is None:
            return {}
        if isinstance(v, str):
            import json

            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return {}
        if isinstance(v, dict):
            return v
        return {}


class BookWithProgress(BookResponse):
    """Schema for book with progress information."""

    progress: BookProgressResponse | None = None


class BookChapterBase(CamelModel):
    """Base schema for book chapter."""

    chapter_number: int = Field(ge=1)
    title: str = Field(max_length=500)
    start_page: int | None = Field(None, ge=1)
    end_page: int | None = Field(None, ge=1)
    status: BookLearningStatus = "not_started"


class BookChapterResponse(BookChapterBase):
    """Schema for book chapter response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    book_id: uuid.UUID
    created_at: datetime | None = None  # None if not from database
    updated_at: datetime | None = None  # None if not from database


class BookChapterStatusUpdate(CamelModel):
    """Schema for updating book chapter status."""

    status: BookLearningStatus


class BookChapterBatchStatusUpdate(CamelModel):
    """Schema for batch updating book chapter statuses."""

    chapter_id: uuid.UUID
    status: BookLearningStatus


# Update forward references
TableOfContentsItem.model_rebuild()
BookTocChapterResponse.model_rebuild()
