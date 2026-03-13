"""Book progress service for tracking reading progress."""

import json
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.exceptions import NotFoundError
from src.progress.models import ProgressUpdate
from src.progress.protocols import ProgressTracker
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


class BookProgressRecomputeError(RuntimeError):
    """Raised when ToC-based completion percentage recomputation fails."""


class BookProgressService(ProgressTracker):
    """Progress service for books implementing ProgressTracker."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _require_owned_book(self, *, content_id: uuid.UUID, user_id: uuid.UUID, operation: str) -> Book:
        book_query = select(Book).where(Book.id == content_id, Book.user_id == user_id)
        book_result = await self._session.execute(book_query)
        book = book_result.scalar_one_or_none()
        if book is None:
            logger.warning(
                "books.access_denied",
                extra={"user_id": str(user_id), "book_id": str(content_id), "operation": operation},
            )
            resource_type = "book"
            raise NotFoundError(resource_type, str(content_id))
        return book

    async def _recompute_completion_percentage(
        self,
        *,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        book: Book,
        toc_progress: dict[str, Any],
        operation: str,
    ) -> float:
        """Recompute completion percentage and raise a typed error on invalid ToC progress data."""
        try:
            recomputed_percentage = await self.get_book_toc_progress_percentage(
                content_id,
                user_id,
                book,
                toc_progress,
            )
        except (TypeError, ValueError, ZeroDivisionError) as error:
            logger.warning(
                "Failed to recompute book progress percentage",
                extra={
                    "user_id": str(user_id),
                    "book_id": str(content_id),
                    "operation": operation,
                    "error": str(error),
                },
            )
            message = f"Failed to recompute book progress percentage during {operation}"
            raise BookProgressRecomputeError(message) from error

        return float(recomputed_percentage)

    async def initialize_progress(self, content_id: uuid.UUID, user_id: uuid.UUID, total_pages: int = 0) -> None:
        """Initialize progress tracking for a new book."""
        progress_service = ProgressService(self._session)
        metadata = {
            "current_page": 1,
            "total_pages": total_pages,
            "toc_progress": {},
            "bookmarks": [],
            "content_type": "book",
        }
        progress_update = ProgressUpdate(progress_percentage=0, metadata=metadata)

        await progress_service.update_progress(
            user_id=user_id,
            content_id=content_id,
            content_type="book",
            progress=progress_update,
        )

    async def get_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Get progress data for a specific book and user."""
        progress_service = ProgressService(self._session)
        progress_data = await progress_service.get_single_progress(user_id, content_id)

        book_query = select(Book).where(Book.id == content_id, Book.user_id == user_id)
        book_result = await self._session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if book is None:
            logger.warning(
                "books.access_denied",
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

        metadata = progress_data.metadata or {}
        toc_progress = metadata.get("toc_progress", {})
        progress_percentage = progress_data.progress_percentage or 0

        if book and book.table_of_contents and toc_progress and progress_percentage == 0:
            progress_percentage = await self._recompute_completion_percentage(
                content_id=content_id,
                user_id=user_id,
                book=book,
                toc_progress=toc_progress,
                operation="get_progress",
            )

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

    async def update_progress(self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update progress data for a specific book and user."""
        progress_service = ProgressService(self._session)
        current_progress = await progress_service.get_single_progress(user_id, content_id)
        metadata = current_progress.metadata if current_progress else {}
        completion_percentage = current_progress.progress_percentage if current_progress else 0
        book: Book | None = None

        if "page" in progress_data and progress_data["page"] is not None:
            book = await self._require_owned_book(content_id=content_id, user_id=user_id, operation="update_progress")
            metadata["current_page"] = progress_data["page"]
            total_pages_value = book.total_pages or 0
            if total_pages_value > 0:
                page_based_percentage = (progress_data["page"] / total_pages_value) * 100
                completion_percentage = min(page_based_percentage, 100.0)

        if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
            completion_percentage = progress_data["completion_percentage"]

        if "toc_progress" in progress_data:
            if book is None:
                book = await self._require_owned_book(content_id=content_id, user_id=user_id, operation="update_progress")

            existing_toc_progress = metadata.get("toc_progress", {})
            if isinstance(existing_toc_progress, dict) and isinstance(progress_data["toc_progress"], dict):
                merged_progress = existing_toc_progress.copy()
                merged_progress.update(progress_data["toc_progress"])
                metadata["toc_progress"] = merged_progress
            else:
                metadata["toc_progress"] = progress_data["toc_progress"]

            if book.table_of_contents and metadata["toc_progress"]:
                completion_percentage = await self._recompute_completion_percentage(
                    content_id=content_id,
                    user_id=user_id,
                    book=book,
                    toc_progress=metadata["toc_progress"],
                    operation="update_progress",
                )

        if "zoom_level" in progress_data:
            metadata["zoom_level"] = progress_data["zoom_level"]

        if "bookmarks" in progress_data:
            metadata["bookmarks"] = progress_data["bookmarks"]

        metadata["content_type"] = "book"
        progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)
        updated = await progress_service.update_progress(user_id, content_id, "book", progress_update)

        return {
            "page": metadata.get("current_page", 0),
            "completion_percentage": updated.progress_percentage,
            "toc_progress": metadata.get("toc_progress", {}),
            "last_accessed_at": updated.updated_at,
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }

    async def calculate_completion_percentage(self, content_id: uuid.UUID, user_id: uuid.UUID) -> float:
        """Calculate completion percentage for a user's book progress."""
        progress = await self.get_progress(content_id, user_id)
        return float(progress.get("completion_percentage", 0.0))

    async def mark_chapter_complete(
        self,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_id: str,
        completed: bool = True,
    ) -> None:
        """Mark a book chapter as complete or incomplete."""
        progress_service = ProgressService(self._session)
        current_progress = await progress_service.get_single_progress(user_id, content_id)
        metadata = current_progress.metadata if current_progress else {}
        toc_progress = metadata.get("toc_progress", {})

        if completed:
            toc_progress[chapter_id] = True
        else:
            toc_progress.pop(chapter_id, None)

        metadata["toc_progress"] = toc_progress
        book = await self._require_owned_book(content_id=content_id, user_id=user_id, operation="mark_chapter_complete")

        completion_percentage = 0
        if book.table_of_contents:
            completion_percentage = await self._recompute_completion_percentage(
                content_id=content_id,
                user_id=user_id,
                book=book,
                toc_progress=toc_progress,
                operation="mark_chapter_complete",
            )

        progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)
        await progress_service.update_progress(user_id, content_id, "book", progress_update)

    async def get_book_toc_progress_percentage(
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
        book: Any | None = None,
        toc_progress: dict[str, Any] | None = None,
    ) -> int:
        """Calculate book progress based on completed leaf sections."""
        if book is None or toc_progress is None:
            progress_service = ProgressService(self._session)
            progress_data = await progress_service.get_single_progress(user_id, book_id)
            if not progress_data or not progress_data.metadata:
                return 0

            toc_progress = progress_data.metadata.get("toc_progress", {})
            book_query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
            book_result = await self._session.execute(book_query)
            book = book_result.scalar_one_or_none()
            if not book or not book.table_of_contents:
                return 0

        safe_toc_progress: dict[str, Any] = toc_progress or {}
        if not safe_toc_progress or not book or not book.table_of_contents:
            return 0
        return self._calculate_toc_percentage(book, safe_toc_progress)

    def _calculate_toc_percentage(self, book: Any, toc_progress: dict[str, Any]) -> int:
        """Calculate progress percentage from TOC data."""
        try:
            toc = json.loads(book.table_of_contents) if isinstance(book.table_of_contents, str) else book.table_of_contents
        except (json.JSONDecodeError, TypeError):
            return 0

        total_sections = 0
        completed_sections = 0

        def count_sections_single_pass(toc_items: list[Any]) -> None:
            nonlocal total_sections, completed_sections
            for item in toc_items:
                if isinstance(item, dict) and item.get("id"):
                    children = item.get("children", [])
                    if not children:
                        total_sections += 1
                        if toc_progress.get(str(item["id"])) is True:
                            completed_sections += 1
                    else:
                        count_sections_single_pass(children)

        count_sections_single_pass(toc)
        if total_sections == 0:
            return 0
        return int((completed_sections / total_sections) * 100)
