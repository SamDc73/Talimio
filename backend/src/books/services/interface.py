"""Interface definition for BookService using Protocol for type checking."""

from typing import Protocol
from uuid import UUID

from fastapi import BackgroundTasks, UploadFile

from src.books.schemas import (
    BookChapterResponse,
    BookCreate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
)


class IBookService(Protocol):
    """Interface for unified book service operations.

    This interface defines all the operations that should be supported
    by any book service implementation, allowing for easy testing
    and migration between different implementations.
    """

    # Book CRUD operations
    async def create_book(
        self, book_data: BookCreate, file: UploadFile, background_tasks: BackgroundTasks
    ) -> BookResponse:
        """Create a new book with uploaded file."""
        ...

    async def get_books(self, page: int = 1, per_page: int = 20) -> BookListResponse:
        """Get list of books with pagination."""
        ...

    async def get_book(self, book_id: UUID) -> BookWithProgress:
        """Get a book by ID with progress information."""
        ...

    async def update_book(self, book_id: UUID, book_data: BookUpdate) -> BookResponse:
        """Update a book."""
        ...

    # Progress operations
    async def update_book_progress(self, book_id: UUID, progress_data: BookProgressUpdate) -> BookProgressResponse:
        """Update reading progress for a book."""
        ...

    # Chapter operations
    async def get_book_chapters(self, book_id: UUID) -> list[BookChapterResponse]:
        """Get all chapters for a book."""
        ...

    async def get_book_chapter(self, book_id: UUID, chapter_id: UUID) -> BookChapterResponse:
        """Get a specific chapter for a book."""
        ...

    async def update_book_chapter_status(
        self, book_id: UUID, chapter_id: UUID, chapter_status: str
    ) -> BookChapterResponse:
        """Update the status of a book chapter."""
        ...

    async def extract_and_create_chapters(self, book_id: UUID) -> list[BookChapterResponse]:
        """Extract chapters from book's table of contents and create chapter records."""
        ...

    async def batch_update_chapter_statuses(
        self, book_id: UUID, updates: list[dict[str, str]]
    ) -> list[BookChapterResponse]:
        """Update multiple chapter statuses in one transaction."""
        ...

    # Metadata operations
    async def extract_and_update_toc(self, book_id: UUID) -> BookResponse:
        """Extract and update table of contents for an existing book."""
        ...
