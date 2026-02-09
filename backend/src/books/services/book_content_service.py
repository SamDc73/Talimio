"""Book content service for book-specific operations."""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book


logger = logging.getLogger(__name__)


class BookContentService:
    """Book service handling book-specific content operations (stateless)."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_book(self, data: dict[str, Any], user_id: UUID) -> Book:
        """Create a new book with user isolation."""
        # Convert tags to JSON if present
        if "tags" in data and data["tags"] is not None:
            data["tags"] = json.dumps(data["tags"])

        return await self._create_with_session(self._session, data, user_id)

    async def _create_with_session(self, session: AsyncSession, data: dict[str, Any], user_id: UUID) -> Book:
        existing_book: Book | None = None
        file_hash = data.get("file_hash")
        if file_hash:
            # Check for duplicate in user's library only
            result = await session.execute(select(Book).where(Book.file_hash == file_hash, Book.user_id == user_id))
            existing_book = result.scalar_one_or_none()

        if existing_book is not None:
            await session.refresh(existing_book)
            logger.info("Reusing existing book", extra={"user_id": str(user_id), "book_id": str(existing_book.id)})
            return existing_book

        # Create book instance
        book = Book(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

        session.add(book)
        await session.flush()
        await session.refresh(book)

        logger.info("Book created", extra={"user_id": str(user_id), "book_id": str(book.id), "title": book.title})
        return book

    async def update_book(self, book_id: UUID, data: dict, user_id: UUID) -> Book:
        """Update an existing book with ownership validation."""
        # Get the book with user isolation
        query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
        result = await self._session.execute(query)
        book = result.scalar_one_or_none()

        if not book:
            logger.warning(
                "BOOK_ACCESS_DENIED",
                extra={"user_id": str(user_id), "book_id": str(book_id), "operation": "update"},
            )
            msg = f"Book {book_id} not found"
            raise ValueError(msg)

        # Update fields
        for field, value in data.items():
            if (field == "tags" and value is not None) or (field == "table_of_contents" and value is not None):
                setattr(book, field, json.dumps(value))
            else:
                setattr(book, field, value)

        book.updated_at = datetime.now(UTC)

        await self._session.flush()
        await self._session.refresh(book)

        logger.info("Book updated", extra={"user_id": str(user_id), "book_id": str(book.id)})
        return book
