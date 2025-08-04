"""Books Module Facade.

Single entry point for all book-related operations.
Coordinates internal book services and provides stable API for other modules.
"""

import logging
from typing import Any
from uuid import UUID

from src.ai.ai_service import get_ai_service
from src.core.interfaces import ContentFacade

from .service import BookService
from .services.book_content_service import BookContentService
from .services.book_progress_tracker import BookProgressTracker


logger = logging.getLogger(__name__)


class BooksFacade(ContentFacade):
    """
    Single entry point for all book operations.

    Coordinates internal book services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Internal services - not exposed to outside modules
        self._book_service = BookService()
        self._content_service = BookContentService()  # New base service
        self._progress_service = BookProgressTracker()  # Implements ProgressTracker protocol
        self._ai_service = get_ai_service()

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get book with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_book_with_progress(content_id, user_id)

    async def get_book_with_progress(self, book_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get complete book information with progress.

        Coordinates book service and progress service to provide comprehensive data.
        """
        try:
            # Get book information - need to pass user_id as well
            # Create a temporary session for the book service call
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                book_response = await self._book_service.get_book(session, str(book_id), user_id)
                # Convert response to dict
                book = book_response.model_dump() if book_response else None

            if not book:
                return {"error": "Book not found"}

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
            return {"error": "Failed to retrieve book"}

    async def create_content(self, content_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new book content.

        Implements ContentFacade interface.
        """
        return await self.create_book(content_data, user_id)

    async def create_book(self, book_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new book entry.

        Handles book creation and coordinates all related operations.
        """
        try:
            # Use the new content service which handles tags, progress, and AI processing
            book = await self._content_service.create_content(book_data, user_id)

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
            # Process book file and extract metadata
            book_data = await self._book_service.process_book_upload(
                file_path, title, user_id, additional_metadata=metadata or {}
            )

            if not book_data.get("success"):
                return book_data

            book_id = book_data["book"]["id"]

            # Initialize progress tracking
            try:
                await self._progress_service.initialize_progress(
                    book_id, user_id, total_pages=book_data["book"].get("total_pages", 0)
                )
            except Exception as e:
                logger.warning(f"Failed to initialize progress tracking: {e}")
                # Don't fail the upload if progress init fails

            return book_data

        except Exception as e:
            logger.exception(f"Error uploading book {title} for user {user_id}: {e}")
            return {"error": f"Failed to upload book: {e!s}", "success": False}

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update book reading progress.

        Implements ContentFacade interface.
        """
        return await self.update_book_progress(content_id, user_id, progress_data)

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

    async def delete_content(self, content_id: UUID, user_id: UUID) -> bool:
        """
        Delete book content.

        Implements ContentFacade interface.
        """
        return await self.delete_book(content_id, user_id)

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
            results = await self._book_service.search_books(query, user_id, filters or {})

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
            books = await self._book_service.get_user_books(user_id)

            # Convert to dict format for progress addition
            book_dicts = []
            for book in books:
                book_dict = book.model_dump()

                if include_progress:
                    # Add progress information to each book
                    progress = await self._progress_service.get_progress(book.id, user_id)
                    book_dict["progress"] = progress

                book_dicts.append(book_dict)

            return {"books": book_dicts, "success": True}

        except Exception as e:
            logger.exception(f"Error getting books for user {user_id}: {e}")
            return {"error": f"Failed to get books: {e!s}", "success": False}

    async def get_book_chapters(self, book_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get book chapters/table of contents if available."""
        try:
            # Get database session
            from src.database.session import async_session_maker

            async with async_session_maker() as db:
                # Get chapters - pass db, book_id, and user_id (following video service pattern)
                try:
                    chapters = await self._book_service.get_book_chapters(db, str(book_id), user_id)
                except ValueError:
                    # Book not found
                    logger.info(f"Book {book_id} not found for user {user_id}")
                    return {"error": f"Book {book_id} not found", "success": False}

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
    async def ask_book_question(self, book_id: UUID, user_id: UUID, question: str, page: int | None = None) -> str:
        """Ask a question about the book content."""
        try:
            await self._ai_service.process_content(
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

    async def summarize_book(self, book_id: UUID, user_id: UUID, page_range: tuple[int, int] | None = None) -> str:
        """Generate a summary of the book."""
        try:
            await self._ai_service.process_content(
                content_type="book", action="summarize", user_id=user_id, book_id=str(book_id), page_range=page_range
            )
        except Exception:
            logger.exception("Error summarizing book %s", book_id)
            raise

    async def chat_about_book(
        self, book_id: UUID, user_id: UUID, message: str, history: list[dict[str, Any]] | None = None
    ) -> str:
        """Have a conversation about the book."""
        try:
            await self._ai_service.process_content(
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

    async def process_book_for_rag(self, book_id: UUID, user_id: UUID, file_path: str) -> dict[str, Any]:
        """Process book content for RAG indexing."""
        try:
            await self._ai_service.process_content(
                content_type="book", action="process_rag", user_id=user_id, book_id=str(book_id), file_path=file_path
            )
        except Exception:
            logger.exception("Error processing book %s for RAG", book_id)
            raise
