"""Book progress service for calculating TOC-based progress.

Similar to CourseProgressService but for books using table of contents.
"""

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book, BookProgress
from src.config.settings import DEFAULT_USER_ID


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
            toc = json.loads(book.table_of_contents) if isinstance(book.table_of_contents, str) else book.table_of_contents
        except (json.JSONDecodeError, TypeError):
            return 0

        # Get progress record with toc_progress
        progress_query = select(BookProgress).where(
            BookProgress.book_id == book_id,
            BookProgress.user_id == effective_user_id
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

        def count_sections(items):
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
            return {
                "total_sections": 0,
                "completed_sections": 0,
                "percentage": 0
            }

        # Parse table of contents
        try:
            toc = json.loads(book.table_of_contents) if isinstance(book.table_of_contents, str) else book.table_of_contents
        except (json.JSONDecodeError, TypeError):
            return {
                "total_sections": 0,
                "completed_sections": 0,
                "percentage": 0
            }

        # Get progress record
        progress_query = select(BookProgress).where(
            BookProgress.book_id == book_id,
            BookProgress.user_id == effective_user_id
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        toc_progress = progress.toc_progress if progress else {}
        total_sections, completed_sections = self._count_toc_progress(toc, toc_progress)

        percentage = int((completed_sections / total_sections) * 100) if total_sections > 0 else 0

        return {
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "percentage": percentage
        }
