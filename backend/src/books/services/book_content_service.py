"""Book content service for book-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select

from src.books.models import Book


logger = logging.getLogger(__name__)


class BookContentService:
    """Book service handling book-specific content operations (stateless)."""

    async def create_book(self, data: dict, user_id: UUID) -> Book:
        """Create a new book with user isolation."""
        from src.database.session import async_session_maker

        # Convert tags to JSON if present
        if "tags" in data and data["tags"] is not None:
            data["tags"] = json.dumps(data["tags"])

        async with async_session_maker() as session:
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
            await session.commit()
            await session.refresh(book)

            logger.info("Book created", extra={"user_id": str(user_id), "book_id": str(book.id), "title": book.title})
            return book

    async def update_book(self, book_id: UUID, data: dict, user_id: UUID) -> Book:
        """Update an existing book with ownership validation."""
        from src.database.session import async_session_maker

        async with async_session_maker() as session:
            # Get the book with user isolation
            query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
            result = await session.execute(query)
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

            await session.commit()
            await session.refresh(book)

            logger.info("Book updated", extra={"user_id": str(user_id), "book_id": str(book.id)})
            return book

