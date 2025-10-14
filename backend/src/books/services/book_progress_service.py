"""Book progress service for tracking reading progress."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.books.models import Book
from src.database.session import async_session_maker
from src.progress.models import ProgressUpdate
from src.progress.protocols import ProgressTracker
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


class BookProgressService(ProgressTracker):
    """Stateless progress service for books implementing ProgressTracker."""

    async def initialize_progress(self, content_id: UUID, user_id: UUID, total_pages: int = 0) -> None:
        """Initialize progress tracking for a new book."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)

            metadata = {
                "current_page": 1,
                "total_pages": total_pages,
                "toc_progress": {},
                "bookmarks": [],
                "content_type": "book",
            }
            progress_update = ProgressUpdate(progress_percentage=0, metadata=metadata)

            await progress_service.update_progress(
                user_id=user_id, content_id=content_id, content_type="book", progress=progress_update
            )

            logger.info(
                "Book progress initialized",
                extra={"user_id": str(user_id), "book_id": str(content_id), "total_pages": total_pages},
            )

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific book and user."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, content_id)

            # Get book for total pages with user isolation
            book_query = select(Book).where(Book.id == content_id, Book.user_id == user_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(user_id), "book_id": str(content_id), "operation": "get_progress"},
                )

            total_pages = book.total_pages if book else 0

            if not progress_data:
                return {
                    "page": 0,
                    "total_pages": total_pages,
                    "completion_percentage": 0,
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
                    progress_percentage = await self.get_book_toc_progress_percentage(
                        content_id, user_id, book, toc_progress
                    )
                except Exception as e:  # pragma: no cover - best-effort fallback
                    logger.warning(
                        "Failed to calculate book progress percentage",
                        extra={"user_id": str(user_id), "book_id": str(content_id), "error": str(e)},
                    )
                    progress_percentage = 0

            return {
                "page": metadata.get("current_page", 0),
                "total_pages": total_pages,
                "completion_percentage": progress_percentage,
                "toc_progress": toc_progress,
                "bookmarks": metadata.get("bookmarks", []),
                "last_accessed_at": progress_data.updated_at,
                "created_at": progress_data.created_at,
                "updated_at": progress_data.updated_at,
            }

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update progress data for specific book and user."""
        async with async_session_maker() as session:
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
                book_query = select(Book).where(Book.id == content_id, Book.user_id == user_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if book and book.total_pages > 0:
                    page_based_percentage = (progress_data["page"] / book.total_pages) * 100
                    completion_percentage = min(page_based_percentage, 100.0)

            if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
                completion_percentage = progress_data["completion_percentage"]

            if "toc_progress" in progress_data:
                # Merge incoming toc_progress with existing, don't replace
                existing_toc_progress = metadata.get("toc_progress", {})
                if isinstance(existing_toc_progress, dict) and isinstance(progress_data["toc_progress"], dict):
                    merged_progress = existing_toc_progress.copy()
                    merged_progress.update(progress_data["toc_progress"])
                    metadata["toc_progress"] = merged_progress
                else:
                    metadata["toc_progress"] = progress_data["toc_progress"]

                # Recalculate completion percentage after TOC updates
                book_query = select(Book).where(Book.id == content_id, Book.user_id == user_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if book and book.table_of_contents and metadata["toc_progress"]:
                    try:
                        completion_percentage = await self.get_book_toc_progress_percentage(
                            content_id, user_id, book, metadata["toc_progress"]
                        )
                    except Exception as e:  # pragma: no cover - best-effort fallback
                        logger.warning(
                            "Failed to recalculate book progress percentage",
                            extra={"user_id": str(user_id), "book_id": str(content_id), "error": str(e)},
                        )

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

            logger.info(
                "Book progress updated",
                extra={
                    "user_id": str(user_id),
                    "book_id": str(content_id),
                    "completion_percentage": updated.progress_percentage,
                },
            )

            # Return updated progress in expected format
            return {
                "page": metadata.get("current_page", 0),
                "completion_percentage": updated.progress_percentage,
                "toc_progress": metadata.get("toc_progress", {}),
                "last_accessed_at": updated.updated_at,
                "created_at": updated.created_at,
                "updated_at": updated.updated_at,
            }


    async def mark_chapter_complete(
        self, content_id: UUID, user_id: UUID, chapter_id: str, completed: bool = True
    ) -> None:
        """Mark a book chapter as complete or incomplete."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            # Get current metadata
            metadata = current_progress.metadata if current_progress else {}
            toc_progress = metadata.get("toc_progress", {})

            # Update chapter status
            if completed:
                toc_progress[chapter_id] = True
            else:
                toc_progress.pop(chapter_id, None)

            # Update metadata
            metadata["toc_progress"] = toc_progress

            # Get book for recalculation with user isolation
            book_query = select(Book).where(Book.id == content_id, Book.user_id == user_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            # Recalculate completion percentage
            completion_percentage = 0
            if book and book.table_of_contents:
                try:
                    completion_percentage = await self.get_book_toc_progress_percentage(
                        content_id, user_id, book, toc_progress
                    )
                except Exception as e:  # pragma: no cover - best-effort fallback
                    logger.warning(
                        "Failed to recalculate book progress percentage",
                        extra={"user_id": str(user_id), "book_id": str(content_id), "error": str(e)},
                    )
                    completion_percentage = current_progress.progress_percentage if current_progress else 0

            # Update progress
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)
            await progress_service.update_progress(user_id, content_id, "book", progress_update)

            logger.info(
                "Book chapter completion updated",
                extra={
                    "user_id": str(user_id),
                    "book_id": str(content_id),
                    "chapter_id": chapter_id,
                    "completed": completed,
                },
            )

    # TOC Progress Calculation Methods

    async def get_book_toc_progress_percentage(
        self, book_id: UUID, user_id: UUID, book: Any | None = None, toc_progress: dict | None = None
    ) -> int:
        """Calculate book progress based on completed leaf sections.

        Returns percentage (0-100) based on completed leaf sections.
        """
        start_time = datetime.now(UTC)

        # Get book and progress data if not provided
        if book is None or toc_progress is None:
            async with async_session_maker() as session:
                progress_service = ProgressService(session)
                progress_data = await progress_service.get_single_progress(user_id, book_id)

                if not progress_data or not progress_data.metadata:
                    return 0

                toc_progress = progress_data.metadata.get("toc_progress", {})

                # Get book with TOC and user isolation
                book_query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if not book or not book.table_of_contents:
                    return 0

        # Calculate progress percentage
        percentage = self._calculate_toc_percentage(book, toc_progress)

        elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        logger.info(
            "Book progress calculated",
            extra={
                "user_id": str(user_id),
                "book_id": str(book_id),
                "percentage": percentage,
                "elapsed_ms": elapsed_ms,
            },
        )

        return percentage

    def _calculate_toc_percentage(self, book: Any, toc_progress: dict) -> int:
        """Calculate progress percentage from TOC data."""
        # Parse table of contents
        try:
            toc = (
                json.loads(book.table_of_contents)
                if isinstance(book.table_of_contents, str)
                else book.table_of_contents
            )
        except (json.JSONDecodeError, TypeError):
            return 0

        # Use a single pass to count both total and completed
        total_sections = 0
        completed_sections = 0

        def count_sections_single_pass(toc_items: list) -> None:
            """Single pass to count total and completed leaf sections."""
            nonlocal total_sections, completed_sections

            for item in toc_items:
                if isinstance(item, dict) and item.get("id"):
                    children = item.get("children", [])
                    if not children:
                        # This is a leaf node
                        total_sections += 1
                        if toc_progress.get(str(item["id"])) is True:
                            completed_sections += 1
                    else:
                        # Has children, recurse
                        count_sections_single_pass(children)

        # Single pass through TOC
        count_sections_single_pass(toc)

        if total_sections == 0:
            return 0

        return int((completed_sections / total_sections) * 100)
