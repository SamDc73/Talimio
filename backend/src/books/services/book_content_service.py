"""Book content service extending BaseContentService."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.core.base_service import BaseContentService
from src.database.session import async_session_maker
from src.storage.factory import get_storage_provider


logger = logging.getLogger(__name__)


class BookContentService(BaseContentService):
    """Book service with shared content behavior."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__()
        self.session = session

    def _get_content_type(self) -> str:
        """Return the content type for this service."""
        return "book"

    async def _do_create(self, data: dict, user_id: UUID) -> Book:
        """Create a new book."""
        async with async_session_maker() as session:
            # Convert tags to JSON if present
            if "tags" in data and data["tags"] is not None:
                data["tags"] = json.dumps(data["tags"])

            # Create book instance
            book = Book(
                **data,
                user_id=user_id,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC)
            )

            session.add(book)
            await session.commit()
            await session.refresh(book)

            logger.info(f"Created book {book.id} for user {user_id}")
            return book

    async def _do_update(self, content_id: UUID, data: dict, user_id: UUID) -> Book:
        """Update an existing book."""
        async with async_session_maker() as session:
            # Get the book
            query = select(Book).where(
                Book.id == content_id,
                Book.user_id == user_id
            )
            result = await session.execute(query)
            book = result.scalar_one_or_none()

            if not book:
                msg = f"Book {content_id} not found"
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

    async def _do_delete(self, content_id: UUID, user_id: UUID) -> bool:
        """Delete a book."""
        async with async_session_maker() as session:
            # Get the book
            query = select(Book).where(
                Book.id == content_id,
                Book.user_id == user_id
            )
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
                logger.exception(f"Failed to delete file from storage for book {content_id}: {e}")

            logger.info(f"Deleted book {content_id}")
            return True

    def _needs_ai_processing(self, content: Book) -> bool:
        """Check if book needs AI processing after creation."""
        # Books need AI processing for RAG indexing
        return content.rag_status != "completed"

    def _needs_ai_reprocessing(self, content: Book, updated_data: dict) -> bool:
        """Check if book needs AI reprocessing after update."""
        # Reprocess if content changes that affect RAG
        _ = content
        significant_fields = {"file_path", "title", "author", "description"}
        return any(field in updated_data for field in significant_fields)

    async def _update_progress(self, content_id: UUID, user_id: UUID, status: str) -> None:
        """Update progress tracking for book."""
        _ = user_id
        try:
            # For books, we track reading progress separately
            # This is just for creation status
            logger.info(f"Book {content_id} status: {status}")
        except Exception as e:
            logger.exception(f"Failed to update book progress: {e}")
