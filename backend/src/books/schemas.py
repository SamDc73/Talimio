from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class BookBase(BaseModel):
    """Base schema for book data."""

    title: str = Field(..., max_length=500)
    subtitle: str | None = Field(None, max_length=500)
    author: str = Field(..., max_length=200)
    description: str | None = None
    isbn: str | None = Field(None, max_length=20)
    language: str | None = Field(None, max_length=10)
    publication_year: int | None = Field(None, ge=1000, le=2030)
    publisher: str | None = Field(None, max_length=200)
    tags: list[str] = Field(default_factory=list)


class BookCreate(BookBase):
    """Schema for creating a book."""

    file_type: str = Field(..., pattern="^(pdf|epub)$")


class BookUpdate(BaseModel):
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


class BookResponse(BookBase):
    """Schema for book response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_type: str
    file_size: int
    total_pages: int | None
    cover_image_path: str | None
    created_at: datetime
    updated_at: datetime

    @property
    def tags_list(self) -> list[str]:
        """Convert tags JSON string to list."""
        if isinstance(self.tags, str):
            import json

            try:
                return json.loads(self.tags)
            except (json.JSONDecodeError, TypeError):
                return []
        return self.tags or []


class BookProgressBase(BaseModel):
    """Base schema for book progress."""

    current_page: int = Field(default=1, ge=1)
    progress_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    reading_time_minutes: int = Field(default=0, ge=0)
    status: str = Field(default="not_started", pattern="^(not_started|reading|completed|paused)$")
    notes: str | None = None
    bookmarks: list[int] = Field(default_factory=list)


class BookProgressUpdate(BaseModel):
    """Schema for updating book progress."""

    current_page: int | None = Field(None, ge=1)
    progress_percentage: float | None = Field(None, ge=0.0, le=100.0)
    reading_time_minutes: int | None = Field(None, ge=0)
    status: str | None = Field(None, pattern="^(not_started|reading|completed|paused)$")
    notes: str | None = None
    bookmarks: list[int] | None = None


class BookProgressResponse(BookProgressBase):
    """Schema for book progress response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    book_id: UUID
    user_id: str
    total_pages_read: int
    last_read_at: datetime | None
    created_at: datetime
    updated_at: datetime

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

    books: list[BookResponse]
    total: int
    page: int
    per_page: int
