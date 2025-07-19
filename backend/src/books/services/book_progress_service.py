"""Book progress service for calculating TOC-based progress.

Similar to CourseProgressService but for books using table of contents.
"""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book, BookProgress
from src.books.schemas import BookProgressResponse, BookProgressUpdate


DEFAULT_USER_ID = "default_user"  # For now, use default user (consistent with database)


logger = logging.getLogger(__name__)


class BookProgressService:
    """Service for calculating book progress based on table of contents."""

    def __init__(self, session: AsyncSession, user_id: str | None = None) -> None:
        """Initialize the book progress service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id or DEFAULT_USER_ID

    async def get_book_toc_progress_percentage(self, book_id: UUID, user_id: UUID | str | None = None) -> int:
        """Calculate book progress based on completed TOC sections.

        Returns percentage (0-100) of completed sections.
        This matches the CourseProgressService interface pattern.
        """
        effective_user_id = str(user_id) if user_id else self.user_id

        # Get book with TOC
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book or not book.table_of_contents:
            return 0

        # Parse table of contents
        try:
            toc = (
                json.loads(book.table_of_contents)
                if isinstance(book.table_of_contents, str)
                else book.table_of_contents
            )
        except (json.JSONDecodeError, TypeError):
            return 0

        # Get progress record with toc_progress
        progress_query = select(BookProgress).where(
            BookProgress.book_id == book_id, BookProgress.user_id == effective_user_id
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress or not progress.toc_progress:
            return 0

        # Calculate progress from TOC
        total_sections, completed_sections = self._count_toc_progress(toc, progress.toc_progress)

        if total_sections == 0:
            return 0

        return int((completed_sections / total_sections) * 100)

    def _count_toc_progress(self, toc_items: list, toc_progress: dict) -> tuple[int, int]:
        """Count total and completed sections in table of contents.

        Args:
            toc_items: List of TOC items
            toc_progress: Dict of section_id -> completion status

        Returns
        -------
            Tuple of (total_sections, completed_sections)
        """
        total = 0
        completed = 0
        seen_ids = set()

        def count_sections(items: list[dict]) -> None:
            nonlocal total, completed
            for item in items:
                # Skip if we've already seen this ID (handles duplicates)
                if item.get("id") in seen_ids:
                    continue

                seen_ids.add(item.get("id"))
                total += 1

                # Check if this section is completed
                if toc_progress.get(item.get("id"), False):
                    completed += 1

                # Recursively count children
                if item.get("children"):
                    count_sections(item["children"])

        if isinstance(toc_items, list):
            count_sections(toc_items)
        else:
            count_sections([toc_items])

        return total, completed

    async def get_toc_completion_stats(self, book_id: UUID, user_id: UUID | str | None = None) -> dict:
        """Get detailed TOC completion statistics.

        Similar to CourseProgressService.get_lesson_completion_stats
        """
        effective_user_id = str(user_id) if user_id else self.user_id

        # Get book with TOC
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book or not book.table_of_contents:
            return {"total_sections": 0, "completed_sections": 0, "percentage": 0}

        # Parse table of contents
        try:
            toc = (
                json.loads(book.table_of_contents)
                if isinstance(book.table_of_contents, str)
                else book.table_of_contents
            )
        except (json.JSONDecodeError, TypeError):
            return {"total_sections": 0, "completed_sections": 0, "percentage": 0}

        # Get progress record
        progress_query = select(BookProgress).where(
            BookProgress.book_id == book_id, BookProgress.user_id == effective_user_id
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        toc_progress = progress.toc_progress if progress else {}
        total_sections, completed_sections = self._count_toc_progress(toc, toc_progress)

        percentage = int((completed_sections / total_sections) * 100) if total_sections > 0 else 0

        return {"total_sections": total_sections, "completed_sections": completed_sections, "percentage": percentage}

    async def update_book_progress(self, book_id: UUID, progress_data: BookProgressUpdate) -> BookProgressResponse:
        """Update reading progress for a book.

        Args:
            book_id: Book ID
            progress_data: Progress update data

        Returns
        -------
            BookProgressResponse: Updated progress data

        Raises
        ------
            HTTPException: If book not found or update fails
        """
        try:
            # Check if book exists
            book_query = select(Book).where(Book.id == book_id)
            book_result = await self.session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Find or create progress record
            progress_query = select(BookProgress).where(
                BookProgress.book_id == book_id,
                BookProgress.user_id == self.user_id,
            )
            progress_result = await self.session.execute(progress_query)
            progress = progress_result.scalar_one_or_none()

            if not progress:
                progress = BookProgress(
                    book_id=book_id,
                    user_id=self.user_id,
                )
                self.session.add(progress)

            # Update progress fields
            update_data = progress_data.model_dump(exclude_unset=True)
            # logger.info(f"Updating book {book_id} progress for user {self.user_id}: {update_data}")

            for field, value in update_data.items():
                if field == "bookmarks" and value is not None:
                    setattr(progress, field, json.dumps(value))
                elif field == "toc_progress" and value is not None:
                    # logger.info(f"Updating toc_progress. Received value: {value}")
                    # Merge the new toc_progress with the existing one
                    existing_toc_progress = progress.toc_progress or {}
                    if isinstance(existing_toc_progress, str):
                        try:
                            existing_toc_progress = json.loads(existing_toc_progress)
                        except json.JSONDecodeError:
                            existing_toc_progress = {}

                    # logger.info(f"Existing toc_progress: {existing_toc_progress}")

                    if isinstance(value, str):
                        try:
                            parsed_value = json.loads(value)
                            value = parsed_value
                        except json.JSONDecodeError:
                            value = {}

                    if isinstance(existing_toc_progress, dict) and isinstance(value, dict):
                        existing_toc_progress.update(value)
                        setattr(progress, field, existing_toc_progress)
                        # logger.info(f"Merged toc_progress: {existing_toc_progress}")
                    else:
                        # Fallback if types are not as expected
                        setattr(progress, field, value)
                        logger.warning(f"toc_progress update fallback used. Value: {value}")
                else:
                    setattr(progress, field, value)

            # Update current_page if provided
            if progress_data.current_page is not None:
                progress.current_page = progress_data.current_page
                current_total = progress.total_pages_read if progress.total_pages_read is not None else 0
                progress.total_pages_read = max(current_total, progress_data.current_page)

                # Calculate progress percentage based on current page vs total pages
                # Only auto-calculate if progress_percentage wasn't explicitly provided
                if progress_data.progress_percentage is None and book.total_pages and book.total_pages > 0:
                    progress.progress_percentage = (progress_data.current_page / book.total_pages) * 100
                    # Ensure it doesn't exceed 100%
                    progress.progress_percentage = min(progress.progress_percentage, 100.0)

            # Update progress_percentage if explicitly provided
            if progress_data.progress_percentage is not None:
                progress.progress_percentage = progress_data.progress_percentage

            progress.last_read_at = datetime.now(UTC)
            progress.updated_at = datetime.now(UTC)

            await self.session.commit()
            await self.session.refresh(progress)

            return BookProgressResponse.model_validate(progress)

        except HTTPException:
            raise
        except Exception as e:
            logging.exception(f"Error updating book progress for {book_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update book progress: {e!s}",
            ) from e
