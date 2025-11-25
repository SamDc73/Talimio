"""Books Module Facade.

Single entry point for all book-related operations.
Coordinates internal book services and provides a stable API for other modules.
Stateless: no session or user state bound to the instance.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select

from src.books.models import Book
from src.books.schemas import BookResponse, BookWithProgress
from src.database.session import async_session_maker

from .services.book_content_service import BookContentService
from .services.book_progress_service import BookProgressService
from .services.book_response_builder import BookResponseBuilder


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)


class BooksFacade:
    """
    Single entry point for all book operations (stateless).

    Coordinates internal book services, publishes events, and provides
    a stable API without binding to request-scoped state.
    """

    def __init__(self) -> None:
        # Internal services - stateless
        self._content_service = BookContentService()
        self._progress_service = BookProgressService()

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get book with progress in a dict structure (parity with other facades)."""
        try:
            book_with = await self.get_book(content_id, user_id)
        except Exception:
            return {"error": "Book not found", "success": False}

        # Also retrieve unified progress to ensure core fields are present
        try:
            progress = await self._progress_service.get_progress(content_id, user_id)
        except Exception:
            progress = None

        return {
            "book": book_with.model_dump(),
            "progress": (progress or {}),
            "completion_percentage": (progress or {}).get("completion_percentage", 0),
            "success": True,
        }

    async def get_book(self, book_id: UUID, user_id: UUID) -> BookWithProgress:
        """Get a single book with progress as a typed response."""
        try:
            # Ownership-checked book
            async with async_session_maker() as session:
                result = await session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
                book = result.scalar_one_or_none()

            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "operation": "get_book"},
                )
                msg = "Book not found"
                raise ValueError(msg)

            # Recalculate progress using the unified service (ToC-aware)
            prog = await self._progress_service.get_progress(book_id, user_id)
            progress = BookResponseBuilder.build_progress_response(prog, book_id) if prog else None

            return BookResponseBuilder.build_book_with_progress(book, progress)

        except ValueError:
            raise
        except Exception as e:
            logger.exception(
                "Error getting book",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
            )
            raise

    async def upload_book(
        self,
        user_id: UUID,
        file_path: str,
        title: str,
        metadata: dict[str, Any] | None = None,
        *,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """Upload book file to user's library."""
        try:
            # Build book data combining provided metadata and required fields
            data: dict[str, Any] = {**(metadata or {})}
            data["title"] = title or data.get("title")
            data["file_path"] = file_path
            # Ensure RAG status set to pending for processing pipeline
            data.setdefault("rag_status", "pending")

            # Create the book record via content service (prefer request session when provided)
            book = await self._content_service.create_book(data, user_id, session=session)

            book_id = getattr(book, "id", None)
            total_pages = getattr(book, "total_pages", 0)

            # Auto-tag the created book (align with video flow)
            try:
                if book_id:
                    await self._auto_tag_book(book_id, user_id)
            except Exception as e:
                logger.warning(
                    "Automatic tagging failed",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
                )

            # Initialize progress tracking (non-fatal on failure)
            try:
                if book_id:
                    await self._progress_service.initialize_progress(book_id, user_id, total_pages=total_pages)
            except Exception as e:
                logger.warning(
                    "Failed to initialize progress tracking",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
                )

            return {"book": book, "success": True}

        except Exception as e:
            logger.exception("Error uploading book", extra={"user_id": str(user_id), "title": title, "error": str(e)})
            return {"error": f"Failed to upload book: {e!s}", "success": False}

    async def _auto_tag_book(self, book_id: UUID, user_id: UUID) -> list[str]:
        """Generate tags for a book using its content preview and store them."""
        try:
            # Defer imports to avoid circular dependencies and keep facade lightweight
            from src.tagging.processors.book_processor import process_book_for_tagging
            from src.tagging.service import TaggingService

            async with async_session_maker() as session:
                # Extract content preview for tagging
                content_data = await process_book_for_tagging(str(book_id), session)
                if not content_data:
                    logger.warning(
                        "Book not found or no content data for tagging",
                        extra={"user_id": str(user_id), "book_id": str(book_id)},
                    )
                    return []

                # Generate tags via TaggingService
                tagging_service = TaggingService(session)
                tags = await tagging_service.tag_content(
                    content_id=book_id,
                    content_type="book",
                    user_id=user_id,
                    title=content_data.get("title", ""),
                    content_preview=content_data.get("content_preview", ""),
                )

                # Persist tags onto the Book model for backward compatibility
                if tags:
                    db_book = await session.get(Book, book_id)
                    if db_book:
                        db_book.tags = json.dumps(tags)
                        await session.commit()
                        logger.info(
                            "Book tagged successfully",
                            extra={"user_id": str(user_id), "book_id": str(book_id), "tag_count": len(tags)},
                        )
                else:
                    # Still commit any flushed tag associations inside TaggingService
                    await session.commit()

                return tags or []

        except Exception as e:
            logger.exception(
                "Auto-tagging error", extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)}
            )
            return []

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update book reading progress (stateless signature)."""
        try:
            # Update progress using the progress tracker
            updated_progress = await self._progress_service.update_progress(content_id, user_id, progress_data)

            if "error" in updated_progress:
                return {"error": updated_progress["error"], "success": False}

            return {"progress": updated_progress, "success": True}

        except Exception as e:
            logger.exception(
                "Error updating progress",
                extra={"user_id": str(user_id), "book_id": str(content_id), "error": str(e)},
            )
            return {"error": f"Failed to update progress: {e!s}", "success": False}

    async def update_book(self, book_id: UUID, user_id: UUID, update_data: dict[str, Any]) -> dict[str, Any]:
        """Update book metadata."""
        try:
            # Update through content service which handles tags and reprocessing
            book = await self._content_service.update_book(book_id, update_data, user_id)

            return {"book": book, "success": True}

        except Exception as e:
            logger.exception(
                "Error updating book", extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)}
            )
            return {"error": "Failed to update book", "success": False}

    async def get_user_books(self, user_id: UUID, include_progress: bool = True) -> dict[str, Any]:
        """Get all books for user. Optionally includes progress information."""
        try:
            # Fetch books for this user
            async with async_session_maker() as session:
                result = await session.execute(
                    select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())
                )
                books = list(result.scalars().all())

            # Convert to dict format and optionally add progress
            book_dicts: list[dict[str, Any]] = []
            for book in books:
                book_response = BookResponse.model_validate(book)
                bd = book_response.model_dump()
                if include_progress:
                    progress = await self._progress_service.get_progress(bd["id"], user_id)
                    bd["progress"] = progress
                book_dicts.append(bd)

            return {"books": book_dicts, "success": True}

        except Exception as e:
            logger.exception("Error getting books", extra={"user_id": str(user_id), "error": str(e)})
            return {"error": f"Failed to get books: {e!s}", "success": False}

    async def get_book_chapters(self, book_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get book chapters/table of contents if available."""
        try:
            # Fetch book to read table_of_contents JSON
            async with async_session_maker() as session:
                result = await session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
                book = result.scalar_one_or_none()
            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "operation": "get_chapters"},
                )
                return {"error": f"Book {book_id} not found", "success": False}

            chapters: list[dict] = []
            if getattr(book, "table_of_contents", None):
                try:
                    toc = json.loads(book.table_of_contents)  # type: ignore[arg-type]
                    if isinstance(toc, list):
                        chapters = toc
                except (json.JSONDecodeError, TypeError):
                    chapters = []

            # Add progress information for each chapter
            if chapters:
                progress = await self._progress_service.get_progress(book_id, user_id)
                completed_chapters = progress.get("completed_chapters", {})
                for chapter in chapters:
                    chapter["completed"] = completed_chapters.get(chapter.get("id"), False)

            return {"chapters": chapters or [], "success": True}

        except Exception as e:
            logger.exception(
                "Error getting chapters",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
            )
            return {"error": "Failed to get chapters", "success": False}

    async def mark_chapter_complete(
        self, book_id: UUID, user_id: UUID, chapter_id: str, completed: bool = True
    ) -> dict[str, Any]:
        """Mark a book chapter as completed."""
        try:
            await self._progress_service.mark_chapter_complete(book_id, user_id, chapter_id, completed)
            return {"result": True, "success": True}
        except Exception as e:
            logger.exception(
                "Error marking chapter complete",
                extra={
                    "user_id": str(user_id),
                    "book_id": str(book_id),
                    "chapter_id": chapter_id,
                    "error": str(e),
                },
            )
            return {"error": "Failed to mark chapter complete", "success": False}
