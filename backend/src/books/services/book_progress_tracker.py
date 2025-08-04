"""Book progress tracker implementing the ProgressTracker protocol.

This provides a simplified interface for progress tracking that doesn't
depend on UserContext or session management.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.books.models import Book
from src.core.interfaces import ProgressTracker
from src.database.session import async_session_maker
from src.progress.models import ProgressUpdate
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


class BookProgressTracker(ProgressTracker):
    """Simplified progress tracker for books that implements the ProgressTracker protocol."""

    async def initialize_progress(self, content_id: UUID, user_id: UUID, total_pages: int = 0) -> None:
        """Initialize progress tracking for a new book."""
        async with async_session_maker() as session:
            # Use unified progress service
            progress_service = ProgressService(session)

            # Create initial progress entry
            metadata = {"current_page": 1, "total_pages": total_pages, "toc_progress": {}, "bookmarks": []}

            # Create progress update object
            progress_update = ProgressUpdate(progress_percentage=0, metadata=metadata)

            await progress_service.update_progress(
                user_id=user_id, content_id=content_id, content_type="book", progress=progress_update
            )

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific book and user."""
        async with async_session_maker() as session:
            # Use unified progress service
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, content_id)

            # Get book for total pages
            book_query = select(Book).where(Book.id == content_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            total_pages = book.total_pages if book else 0

            if not progress_data:
                return {
                    "page": 0,
                    "total_pages": total_pages,
                    "completion_percentage": 0,
                    "progress_percentage": 0,  # Add both for compatibility
                    "toc_progress": {},
                    "bookmarks": [],
                }

            # Extract metadata
            metadata = progress_data.metadata or {}
            toc_progress = metadata.get("toc_progress", {})

            # Calculate progress percentage from ToC progress on-demand if needed
            progress_percentage = progress_data.progress_percentage or 0

            if book and book.table_of_contents and toc_progress and progress_percentage == 0:
                try:
                    # Import the progress service to calculate percentage
                    from src.books.services.book_progress_service import BookProgressService

                    service = BookProgressService(session, user_id)
                    progress_percentage = await service.get_book_toc_progress_percentage(content_id, user_id)
                except Exception as e:
                    logger.warning(f"Failed to calculate book progress percentage: {e}")
                    progress_percentage = 0

            return {
                "page": metadata.get("current_page", 0),
                "total_pages": total_pages,
                "completion_percentage": progress_percentage,
                "progress_percentage": progress_percentage,  # Add both for compatibility
                "toc_progress": toc_progress,
                "bookmarks": metadata.get("bookmarks", []),
                "last_accessed_at": progress_data.updated_at,
                "created_at": progress_data.created_at,
                "updated_at": progress_data.updated_at,
            }

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update progress data for specific book and user."""
        async with async_session_maker() as session:
            # Use unified progress service
            progress_service = ProgressService(session)

            # Get current progress
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            # Prepare metadata
            metadata = current_progress.metadata if current_progress else {}
            completion_percentage = current_progress.progress_percentage if current_progress else 0

            # Update metadata fields
            if "page" in progress_data and progress_data["page"] is not None:
                metadata["current_page"] = progress_data["page"]

                # Auto-calculate completion percentage if we have total pages
                book_query = select(Book).where(Book.id == content_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if book and book.total_pages > 0:
                    page_based_percentage = (progress_data["page"] / book.total_pages) * 100
                    completion_percentage = min(page_based_percentage, 100.0)

            if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
                completion_percentage = progress_data["completion_percentage"]

            if "toc_progress" in progress_data:
                metadata["toc_progress"] = progress_data["toc_progress"]

                # Recalculate completion percentage after TOC updates
                # This fixes the stale data bug where percentage wasn't updated
                book_query = select(Book).where(Book.id == content_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if book and book.table_of_contents and progress_data["toc_progress"]:
                    try:
                        from src.books.services.book_progress_service import BookProgressService

                        book_service = BookProgressService(session, user_id)
                        new_percentage = await book_service.get_book_toc_progress_percentage(content_id, user_id)
                        completion_percentage = new_percentage
                    except Exception as e:
                        logger.warning(f"Failed to recalculate book progress percentage: {e}")
                        # Keep existing percentage on error

            # Update zoom level if provided
            if "zoom_level" in progress_data:
                metadata["zoom_level"] = progress_data["zoom_level"]

            # Update bookmarks if provided
            if "bookmarks" in progress_data:
                metadata["bookmarks"] = progress_data["bookmarks"]

            # Ensure content_type is set in metadata
            metadata["content_type"] = "book"

            # Update using unified progress service
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)

            updated = await progress_service.update_progress(user_id, content_id, "book", progress_update)

            # Return updated progress in expected format
            return {
                "page": metadata.get("current_page", 0),
                "completion_percentage": updated.progress_percentage,
                "toc_progress": metadata.get("toc_progress", {}),
                "last_accessed_at": updated.updated_at,
                "created_at": updated.created_at,
                "updated_at": updated.updated_at,
            }

    async def calculate_completion_percentage(self, content_id: UUID, user_id: UUID) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        progress = await self.get_progress(content_id, user_id)
        return progress.get("completion_percentage", 0.0)

    async def mark_chapter_complete(
        self, content_id: UUID, user_id: UUID, chapter_id: str, completed: bool = True
    ) -> None:
        """Mark a book chapter as complete or incomplete."""
        async with async_session_maker() as session:
            # Get current progress
            progress_service = ProgressService(session)
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            # Get current metadata
            metadata = current_progress.metadata if current_progress else {}
            toc_progress = metadata.get("toc_progress", {})

            # Update chapter status
            if completed:
                toc_progress[chapter_id] = "completed"
            else:
                toc_progress.pop(chapter_id, None)

            # Update metadata
            metadata["toc_progress"] = toc_progress

            # Recalculate completion percentage
            try:
                from src.books.services.book_progress_service import BookProgressService

                book_service = BookProgressService(session, user_id)
                completion_percentage = await book_service.get_book_toc_progress_percentage(content_id, user_id)
            except Exception as e:
                logger.warning(f"Failed to recalculate book progress percentage: {e}")
                completion_percentage = current_progress.progress_percentage if current_progress else 0

            # Update progress
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)

            await progress_service.update_progress(user_id, content_id, "book", progress_update)
