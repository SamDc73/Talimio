"""Book content service for book-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.database.session import async_session_maker
from src.storage.factory import get_storage_provider


logger = logging.getLogger(__name__)


class BookContentService:
    """Book service handling book-specific content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def create_book(self, data: dict, user_id: UUID) -> Book:
        """Create a new book."""
        async with async_session_maker() as session:
            # Convert tags to JSON if present
            if "tags" in data and data["tags"] is not None:
                data["tags"] = json.dumps(data["tags"])

            # Create book instance
            book = Book(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(book)
            await session.commit()
            await session.refresh(book)

            logger.info(f"Created book {book.id} for user {user_id}")
            return book

    async def update_book(self, book_id: UUID, data: dict, user_id: UUID) -> Book:
        """Update an existing book."""
        async with async_session_maker() as session:
            # Get the book
            query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
            result = await session.execute(query)
            book = result.scalar_one_or_none()

            if not book:
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

            logger.info(f"Updated book {book.id}")
            return book

    async def delete_book(self, book_id: UUID, user_id: UUID) -> bool:
        """Delete a book."""
        async with async_session_maker() as session:
            # Get the book
            query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
            result = await session.execute(query)
            book = result.scalar_one_or_none()

            if not book:
                return False

            # Store file path before deletion
            file_path = book.file_path

            # Delete the book (cascade will handle related records)
            await session.delete(book)
            await session.commit()

            # Delete file from storage (R2 or local)
            try:
                storage = get_storage_provider()

                # Delete the main book file
                if file_path:
                    await storage.delete(file_path)
                    logger.info(f"Deleted book file from storage: {file_path}")

            except Exception as e:
                # Log error but don't fail the deletion
                # The database record is already deleted
                logger.exception(f"Failed to delete file from storage for book {book_id}: {e}")

            logger.info(f"Deleted book {book_id}")
            return True
