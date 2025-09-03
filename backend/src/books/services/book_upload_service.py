import logging
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, UploadFile, status

from src.books.schemas import BookCreate, BookResponse


logger = logging.getLogger(__name__)


class BookUploadService:
    """Service for handling book uploads, validation, and storage."""

    def __init__(self, session: Any) -> None:
        """Initialize the book upload service."""
        self.session = session

    async def create_book(
        self, book_data: BookCreate, file: UploadFile, background_tasks: BackgroundTasks, user_id: UUID
    ) -> BookResponse:
        """Deprecate this service path; use BooksFacade.upload_book instead."""
        logger.warning("BookUploadService.create_book was called; this path is deprecated. Use BooksFacade.upload_book")
        # Touch arguments to avoid unused-argument lints while keeping the original signature intact
        _ = (book_data, file, background_tasks, user_id)
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="BookUploadService is deprecated. Use BooksFacade.upload_book",
        )
