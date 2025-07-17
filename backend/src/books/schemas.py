from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BookBase(BaseModel):
    """Base schema for book data."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(..., max_length=500)
    subtitle: str | None = Field(None, max_length=500)
    author: str = Field(..., max_length=200)
    description: str | None = None
    isbn: str | None = Field(None, max_length=20)
    language: str | None = Field(None, max_length=10)
    publication_year: int | None = Field(None, ge=1000, le=2030, alias="publicationYear")
    publisher: str | None = Field(None, max_length=200)
    tags: list[str] = Field(default_factory=list)


class BookCreate(BookBase):
    """Schema for creating a book."""

    file_type: str = Field(..., pattern="^(pdf|epub)$", alias="fileType")


class BookUpdate(BaseModel):
    """Schema for updating a book."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(None, max_length=500)
    subtitle: str | None = Field(None, max_length=500)
    author: str | None = Field(None, max_length=200)
    description: str | None = None
    isbn: str | None = Field(None, max_length=20)
    language: str | None = Field(None, max_length=10)
    publication_year: int | None = Field(None, ge=1000, le=2030, alias="publicationYear")
    publisher: str | None = Field(None, max_length=200)
    tags: list[str] | None = None


class TableOfContentsItem(BaseModel):
    """Schema for table of contents item."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    title: str
    page: int | None = None
    start_page: int | None = Field(None, alias="startPage")
    end_page: int | None = Field(None, alias="endPage")
    level: int = 0  # 0 for chapters, 1 for sections, etc.
    children: list["TableOfContentsItem"] = Field(default_factory=list)


class BookResponse(BaseModel):
    """Schema for book response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    title: str
    subtitle: str | None = None
    author: str
    description: str | None = None
    isbn: str | None = None
    language: str | None = None
    publication_year: int | None = Field(None, alias="publicationYear")
    publisher: str | None = None
    tags: list[str] = Field(default_factory=list)
    file_type: str = Field(alias="fileType")
    file_path: str = Field(alias="filePath")
    file_size: int = Field(alias="fileSize")
    total_pages: int | None = Field(None, alias="totalPages")
    cover_image_path: str | None = Field(None, alias="coverImagePath")
    table_of_contents: list[TableOfContentsItem] | None = Field(None, alias="tableOfContents")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class BookProgressBase(BaseModel):
    """Base schema for book progress."""

    model_config = ConfigDict(populate_by_name=True)

    current_page: int = Field(default=1, ge=1, alias="currentPage")
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0, alias="progressPercentage")
    reading_time_minutes: int = Field(default=0, ge=0, alias="readingTimeMinutes")
    status: str = Field(default="not_started", pattern="^(not_started|reading|completed|paused)$")
    notes: str | None = None
    bookmarks: list[int] = Field(default_factory=list)
    toc_progress: dict[str, bool] = Field(default_factory=dict, alias="tocProgress")  # Maps section IDs to completion status


class BookProgressUpdate(BaseModel):
    """Schema for updating book progress."""

    current_page: int | None = Field(None, ge=1, alias="currentPage")
    progress_percentage: float | None = Field(None, ge=0.0, le=100.0, alias="progressPercentage")
    reading_time_minutes: int | None = Field(None, ge=0, alias="readingTimeMinutes")
    status: str | None = Field(None, pattern="^(not_started|reading|completed|paused)$")
    notes: str | None = None
    bookmarks: list[int] | None = None
    toc_progress: dict[str, bool] | None = Field(None, alias="tocProgress")  # Maps section IDs to completion status


class BookProgressResponse(BookProgressBase):
    """Schema for book progress response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    book_id: UUID = Field(alias="bookId")
    user_id: str = Field(alias="userId")
    total_pages_read: int = Field(alias="totalPagesRead")
    last_read_at: datetime | None = Field(alias="lastReadAt")
    created_at: datetime = Field(alias="createdAt")

    @field_validator("bookmarks", mode="before")
    @classmethod
    def validate_bookmarks(cls, v: str | list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        """Convert bookmarks from JSON string to list."""
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

    updated_at: datetime = Field(alias="updatedAt")

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

    @property
    def bookmarks_list(self) -> list[int]:
        """Convert bookmarks JSON string to list."""
        if isinstance(self.bookmarks, str):
            import json

            try:
                return json.loads(self.bookmarks)
            except (json.JSONDecodeError, TypeError):
                return []
        return self.bookmarks or []


class BookWithProgress(BookResponse):
    """Schema for book with progress information."""

    progress: BookProgressResponse | None = None


class BookListResponse(BaseModel):
    """Schema for book list response."""

    items: list[BookResponse]
    total: int
    page: int
    pages: int


# Chapter schemas for Phase 2.2
class BookChapterBase(BaseModel):
    """Base schema for book chapter."""

    chapter_number: int = Field(..., ge=1, alias="chapterNumber")
    title: str = Field(..., max_length=500)
    start_page: int | None = Field(None, ge=1, alias="startPage")
    end_page: int | None = Field(None, ge=1, alias="endPage")
    status: str = Field(default="not_started", pattern="^(not_started|in_progress|done)$")


class BookChapterResponse(BookChapterBase):
    """Schema for book chapter response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    book_id: UUID = Field(alias="bookId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class BookChapterStatusUpdate(BaseModel):
    """Schema for updating book chapter status."""

    status: str = Field(..., pattern="^(not_started|in_progress|done)$")


class BookChapterBatchStatusUpdate(BaseModel):
    """Schema for batch updating book chapter statuses."""

    chapter_id: UUID = Field(..., alias="chapterId")
    status: str = Field(..., pattern="^(not_started|in_progress|done)$")


class BookChapterBatchUpdateRequest(BaseModel):
    """Schema for batch chapter status update request."""

    updates: list[BookChapterBatchStatusUpdate] = Field(..., min_length=1, max_length=50)


# Update forward references
TableOfContentsItem.model_rebuild()
