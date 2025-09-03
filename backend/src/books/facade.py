"""Books Module Facade.

Single entry point for all book-related operations.
Coordinates internal book services and provides stable API for other modules.
"""

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.ai.ai_service import get_ai_service
from src.books.models import Book

from .services.book_content_service import BookContentService
from .services.book_progress_service import BookProgressService
from .services.book_query_service import BookQueryService


logger = logging.getLogger(__name__)


class BooksFacade:
    """
    Single entry point for all book operations.

    Coordinates internal book services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Internal services - not exposed to outside modules
        self._content_service = BookContentService()  # New base service
        self._progress_service = BookProgressService()  # Handles reading progress tracking
        self._ai_service = get_ai_service()

    async def get_book_with_progress(self, book_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get complete book information with progress.

        Coordinates book service and progress service to provide comprehensive data.
        """
        try:
            # Get book information with progress using query service
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                query_service = BookQueryService(session, user_id)
                book_with_progress = await query_service.get_book_with_progress(book_id)
                book = book_with_progress.model_dump() if book_with_progress else None

            if not book:
                return {"error": "Book not found", "success": False}

            # Get progress information
            progress = await self._progress_service.get_progress(book_id, user_id)

            # Build response
            return {
                "book": book,
                "progress": progress,
                "completion_percentage": progress.get("completion_percentage", 0),
                "current_page": progress.get("current_page", 1),
                "total_pages": book.get("total_pages", 0),
                "completed_chapters": progress.get("completed_chapters", {}),
                "success": True,
            }

        except Exception:
            logger.exception("Error getting book %s for user %s", book_id, user_id)
            return {"error": "Failed to retrieve book", "success": False}

    async def create_book(self, book_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new book entry.

        Handles book creation and coordinates all related operations.
        """
        try:
            # Use the new content service which handles tags, progress, and AI processing
            book = await self._content_service.create_content(book_data, user_id)

            # Auto-tag the created book
            try:
                if getattr(book, "id", None):
                    await self._auto_tag_book(book.id, user_id)
            except Exception as e:
                logger.warning(f"Automatic tagging failed for book {getattr(book, 'id', None)}: {e}")

            return {"book": book, "success": True}

        except Exception:
            logger.exception("Error creating book for user %s", user_id)
            return {"error": "Failed to create book", "success": False}

    async def upload_book(
        self, file_path: str, title: str, user_id: UUID, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Upload book file to user's library.

        Handles file upload, format detection, and metadata extraction.
        """
        try:
            # Build book data combining provided metadata and required fields
            data: dict[str, Any] = {**(metadata or {})}
            data["title"] = title or data.get("title")
            data["file_path"] = file_path
            # Ensure RAG status set to pending for processing pipeline
            data.setdefault("rag_status", "pending")

            # Create the book record via content service
            book = await self._content_service.create_content(data, user_id)

            book_id = getattr(book, "id", None)
            total_pages = getattr(book, "total_pages", 0)

            # Auto-tag the created book (align with video flow)
            try:
                if book_id:
                    await self._auto_tag_book(book_id, user_id)
            except Exception as e:
                logger.warning(f"Automatic tagging failed for book {book_id}: {e}")

            # Initialize progress tracking (non-fatal on failure)
            try:
                if book_id:
                    await self._progress_service.initialize_progress(book_id, user_id, total_pages=total_pages)
            except Exception as e:
                logger.warning(f"Failed to initialize progress tracking: {e}")

            return {"book": book, "success": True}

        except Exception as e:
            logger.exception(f"Error uploading book {title} for user {user_id}: {e}")
            return {"error": f"Failed to upload book: {e!s}", "success": False}

    async def _auto_tag_book(self, book_id: UUID, user_id: UUID) -> list[str]:
        """Generate tags for a book using its content preview and store them.

        This mirrors the video auto-tagging flow: extract a content preview, call TaggingService,
        then persist generated tags to the Book.tags JSON field. Failures are logged but not raised.
        """
        try:
            # Defer imports to avoid circular dependencies and keep facade lightweight
            from src.books.models import Book
            from src.database.session import async_session_maker
            from src.tagging.processors.book_processor import process_book_for_tagging
            from src.tagging.service import TaggingService

            async with async_session_maker() as session:
                # Extract content preview for tagging
                content_data = await process_book_for_tagging(str(book_id), session)
                if not content_data:
                    logger.warning(f"Book {book_id} not found or no content data for tagging")
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
                        logger.info(f"Successfully tagged book {book_id} with {len(tags)} tags")
                else:
                    # Still commit any flushed tag associations inside TaggingService
                    await session.commit()

                return tags or []

        except Exception as e:
            logger.exception(f"Auto-tagging error for book {book_id}: {e}")
            return []

    async def update_book_progress(self, book_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update book reading progress.

        Handles progress updates, page tracking, and completion detection.
        """
        try:
            # Update progress using the progress tracker
            updated_progress = await self._progress_service.update_progress(book_id, user_id, progress_data)

            if "error" in updated_progress:
                return {"error": updated_progress["error"], "success": False}

            return {"progress": updated_progress, "success": True}

        except Exception as e:
            logger.exception(f"Error updating progress for book {book_id}: {e}")
            return {"error": f"Failed to update progress: {e!s}", "success": False}

    async def update_reading_settings(self, book_id: UUID, user_id: UUID, settings: dict[str, Any]) -> dict[str, Any]:
        """Update book reading settings (zoom, theme, etc.)."""
        try:
            # Update reading settings
            updated_settings = await self._progress_service.update_reading_settings(book_id, user_id, settings)

            return {"settings": updated_settings, "success": True}

        except Exception:
            logger.exception("Error updating reading settings for book %s", book_id)
            return {"error": "Failed to update settings", "success": False}

    async def update_book(self, book_id: UUID, user_id: UUID, update_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update book metadata.

        Updates book information and coordinates any needed reprocessing.
        """
        try:
            # Update through content service which handles tags and reprocessing
            book = await self._content_service.update_content(book_id, user_id, update_data)

            return {"book": book, "success": True}

        except Exception:
            logger.exception("Error updating book %s", book_id)
            return {"error": "Failed to update book", "success": False}

    async def delete_book(self, book_id: UUID, user_id: UUID) -> bool:
        """
        Delete book and all related data.

        Coordinates deletion across all book services.
        """
        try:
            # Use content service which handles cleanup of tags and associated data
            return await self._content_service.delete_content(book_id, user_id)

        except Exception:
            logger.exception("Error deleting book %s", book_id)
            return False

    async def search_books(self, query: str, user_id: UUID, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Search user's books.

        Provides unified search across book content and metadata.
        """
        try:
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                query_service = BookQueryService(session, user_id)
                results = await query_service.search_books(query, limit=(filters or {}).get("limit", 20))

            return {"results": results, "success": True}

        except Exception:
            logger.exception("Error searching books for user %s", user_id)
            return {"error": "Search failed", "success": False}

    async def get_user_books(self, user_id: UUID, include_progress: bool = True) -> dict[str, Any]:
        """
        Get all books for user.

        Optionally includes progress information.
        """
        try:
            from src.books.services.book_response_builder import BookResponseBuilder
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                # Fetch books for this user
                result = await session.execute(
                    select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())
                )
                books = list(result.scalars().all())

                # Convert to response objects for consistent schema
                book_responses = BookResponseBuilder.build_book_list(books)

                # Convert to dict format and optionally add progress
                book_dicts: list[dict[str, Any]] = []
                for br in book_responses:
                    bd = br.model_dump()
                    if include_progress:
                        progress = await self._progress_service.get_progress(bd["id"], user_id)
                        bd["progress"] = progress
                    book_dicts.append(bd)

            return {"books": book_dicts, "success": True}

        except Exception as e:
            logger.exception(f"Error getting books for user {user_id}: {e}")
            return {"error": f"Failed to get books: {e!s}", "success": False}

    async def get_book_chapters(self, book_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get book chapters/table of contents if available."""
        try:
            # Get database session
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                # Fetch book to read table_of_contents JSON
                result = await session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
                book = result.scalar_one_or_none()
                if not book:
                    logger.info(f"Book {book_id} not found for user {user_id}")
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

        except Exception:
            logger.exception("Error getting chapters for book %s", book_id)
            return {"error": "Failed to get chapters", "success": False}

    async def mark_chapter_complete(
        self, book_id: UUID, user_id: UUID, chapter_id: str, completed: bool = True
    ) -> dict[str, Any]:
        """Mark a book chapter as completed."""
        try:
            result = await self._progress_service.mark_chapter_complete(book_id, user_id, chapter_id, completed)

            return {"result": result, "success": True}

        except Exception:
            logger.exception("Error marking chapter complete for book %s", book_id)
            return {"error": "Failed to mark chapter complete", "success": False}

    # AI operations
    async def ask_book_question(
        self, book_id: UUID, user_id: UUID, question: str, page: int | None = None
    ) -> dict[str, Any] | None:
        """Ask a question about the book content."""
        try:
            return await self._ai_service.process_content(
                content_type="book",
                action="question",
                user_id=user_id,
                book_id=str(book_id),
                question=question,
                page=page,
            )
        except Exception:
            logger.exception("Error answering question for book %s", book_id)
            raise

    async def summarize_book(
        self, book_id: UUID, user_id: UUID, page_range: tuple[int, int] | None = None
    ) -> dict[str, Any] | None:
        """Generate a summary of the book."""
        try:
            return await self._ai_service.process_content(
                content_type="book", action="summarize", user_id=user_id, book_id=str(book_id), page_range=page_range
            )
        except Exception:
            logger.exception("Error summarizing book %s", book_id)
            raise

    async def chat_about_book(
        self, book_id: UUID, user_id: UUID, message: str, history: list[dict[str, Any]] | None = None
    ) -> dict[str, Any] | None:
        """Have a conversation about the book."""
        try:
            return await self._ai_service.process_content(
                content_type="book",
                action="chat",
                user_id=user_id,
                book_id=str(book_id),
                message=message,
                history=history,
            )
        except Exception:
            logger.exception("Error in book chat for %s", book_id)
            raise

    async def process_book_for_rag(self, book_id: UUID, user_id: UUID, file_path: str) -> dict[str, Any] | None:
        """Process book content for RAG indexing."""
        try:
            return await self._ai_service.process_content(
                content_type="book", action="process_rag", user_id=user_id, book_id=str(book_id), file_path=file_path
            )
        except Exception:
            logger.exception("Error processing book %s for RAG", book_id)
            raise
