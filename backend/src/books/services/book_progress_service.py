"""Book progress service for calculating TOC-based progress.

Similar to CourseProgressService but for books using table of contents.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.books.models import Book, BookProgress
from src.books.schemas import BookProgressResponse, BookProgressUpdate
from src.config.settings import DEFAULT_USER_ID


logger = logging.getLogger(__name__)


class BookProgressService:
    """Service for calculating book progress based on table of contents."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the book progress service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id or DEFAULT_USER_ID

    async def get_book_toc_progress_percentage(self, book_id: UUID, user_id: UUID | None = None) -> int:
        """Calculate book progress based on completed leaf sections (simple calculation).

        Returns percentage (0-100) based on completed leaf sections.
        This matches the ContentProgressService calculation for consistency.
        """
        effective_user_id = user_id if user_id else self.user_id
        start_time = datetime.now(UTC)

        # Get book and progress data
        book, toc_progress = await self._get_book_and_progress_data(book_id, effective_user_id)
        if not book:
            return 0

        # Calculate progress percentage
        percentage = self._calculate_toc_percentage(book, toc_progress)

        elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        logger.info(f"📚 Book {book_id} progress calculation took {elapsed_ms}ms")

        return percentage

    async def _get_book_and_progress_data(self, book_id: UUID, user_id: UUID) -> tuple[Any, dict]:
        """Get book and its progress data."""
        # Get book with TOC
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book or not book.table_of_contents:
            return None, {}

        # Get progress record with toc_progress
        progress_query = select(BookProgress).where(
            BookProgress.book_id == book_id, BookProgress.user_id == user_id
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress or not progress.toc_progress:
            return book, {}

        # Parse toc_progress if it's a string
        toc_progress = progress.toc_progress
        if isinstance(toc_progress, str):
            try:
                toc_progress = json.loads(toc_progress)
            except (json.JSONDecodeError, TypeError):
                toc_progress = {}

        return book, toc_progress

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

        # OPTIMIZATION: Use a single pass to count both total and completed
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

        percentage = int((completed_sections / total_sections) * 100)
        logger.info(f"📚 Book progress: {completed_sections}/{total_sections} sections = {percentage}%")
        return percentage

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

    def _get_chapter_page_range(self, item: dict, siblings: list[dict], index: int, total_pages: int) -> tuple[int, int]:
        """Get the start and end page for a chapter."""
        start_page = int(item.get("page", 0))

        # Find the next sibling to determine end page
        end_page = total_pages  # Default to end of book
        for j in range(index + 1, len(siblings)):
            next_item = siblings[j]
            next_page = next_item.get("page")
            if next_page:
                end_page = int(next_page)
                break

        return start_page, end_page

    def _is_range_processed(self, start: int, end: int, processed_ranges: list[tuple[int, int]]) -> bool:
        """Check if a page range has already been counted."""
        for processed_start, processed_end in processed_ranges:
            # Check for overlap
            if not (end <= processed_start or start >= processed_end):
                return True
        return False

    def _process_toc_chapters(
        self,
        items: list[dict],
        toc_progress: dict,
        total_pages: int,
        processed_ranges: list[tuple[int, int]],
        parent_completed: bool = False
    ) -> int:
        """Process TOC chapters and calculate completed pages."""
        completed_pages = 0

        for i, item in enumerate(items):
            item_id = item.get("id")

            # Check if this item or its parent is marked as completed
            is_completed = parent_completed or toc_progress.get(item_id, False)

            # For completed chapters, calculate their page contribution
            if is_completed:
                start_page, end_page = self._get_chapter_page_range(item, items, i, total_pages)

                # Only count if we haven't already counted these pages
                if not self._is_range_processed(start_page, end_page, processed_ranges):
                    pages_in_chapter = end_page - start_page
                    if pages_in_chapter > 0:
                        completed_pages += pages_in_chapter
                        processed_ranges.append((start_page, end_page))
                        logger.debug(
                            f"Chapter '{item.get('title')}' ({item_id}): "
                            f"pages {start_page}-{end_page} ({pages_in_chapter} pages)"
                        )

            # Process children, inheriting completion status if parent is complete
            if item.get("children"):
                completed_pages += self._process_toc_chapters(
                    item["children"], toc_progress, total_pages, processed_ranges, is_completed
                )

        return completed_pages

    def _calculate_chapter_weighted_progress(self, toc_items: list, toc_progress: dict, total_pages: int) -> int:
        """Calculate progress based on completed chapters weighted by their page count.

        When a chapter is marked complete, we count all its pages toward progress.
        This handles non-linear reading patterns common in technical books.

        Args:
            toc_items: List of TOC items with page numbers
            toc_progress: Dict of section_id -> completion status
            total_pages: Total pages in the book

        Returns
        -------
            Progress percentage (0-100)
        """
        if total_pages == 0:
            return 0

        processed_page_ranges = []  # Track processed ranges to avoid double counting

        # Process the TOC
        items_to_process = toc_items if isinstance(toc_items, list) else [toc_items]
        completed_pages = self._process_toc_chapters(
            items_to_process, toc_progress, total_pages, processed_page_ranges
        )

        progress = int((completed_pages / total_pages) * 100)
        logger.info(f"Chapter-weighted progress: {completed_pages}/{total_pages} pages = {progress}%")
        return min(progress, 100)  # Cap at 100%

    async def get_toc_completion_stats(self, book_id: UUID, user_id: UUID | None = None) -> dict:
        """Get detailed TOC completion statistics.

        Returns both section-based and page-based progress metrics.
        """
        effective_user_id = user_id if user_id else self.user_id

        # Get book with TOC
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book or not book.table_of_contents:
            return {
                "total_sections": 0,
                "completed_sections": 0,
                "section_percentage": 0,
                "page_percentage": 0,
                "completed_pages": 0,
                "total_pages": 0
            }

        # Parse table of contents
        try:
            toc = (
                json.loads(book.table_of_contents)
                if isinstance(book.table_of_contents, str)
                else book.table_of_contents
            )
        except (json.JSONDecodeError, TypeError):
            return {
                "total_sections": 0,
                "completed_sections": 0,
                "section_percentage": 0,
                "page_percentage": 0,
                "completed_pages": 0,
                "total_pages": 0
            }

        # Get progress record
        progress_query = select(BookProgress).where(
            BookProgress.book_id == book_id, BookProgress.user_id == effective_user_id
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        toc_progress = progress.toc_progress if progress else {}

        # Calculate section-based progress
        total_sections, completed_sections = self._count_toc_progress(toc, toc_progress)
        section_percentage = int((completed_sections / total_sections) * 100) if total_sections > 0 else 0

        # Calculate page-based progress
        total_pages = book.total_pages or 0
        page_percentage = 0
        completed_pages = 0

        if total_pages > 0:
            page_percentage = self._calculate_chapter_weighted_progress(toc, toc_progress, total_pages)
            # Estimate completed pages from percentage
            completed_pages = int((page_percentage / 100) * total_pages)

        return {
            "total_sections": total_sections,
            "completed_sections": completed_sections,
            "section_percentage": section_percentage,
            "page_percentage": page_percentage,
            "completed_pages": completed_pages,
            "total_pages": total_pages
        }

    async def _get_or_create_progress(self, book_id: UUID) -> BookProgress:
        """Get existing progress record or create a new one."""
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

        return progress

    def _update_toc_progress(self, progress: BookProgress, toc_progress_value: dict) -> None:
        """Update table of contents progress."""
        existing_toc_progress = progress.toc_progress or {}
        if isinstance(existing_toc_progress, str):
            try:
                existing_toc_progress = json.loads(existing_toc_progress)
            except json.JSONDecodeError:
                existing_toc_progress = {}

        parsed_toc_value = toc_progress_value
        if isinstance(toc_progress_value, str):
            try:
                parsed_value = json.loads(toc_progress_value)
                parsed_toc_value = parsed_value
            except json.JSONDecodeError:
                parsed_toc_value = {}

        if isinstance(existing_toc_progress, dict) and isinstance(parsed_toc_value, dict):
            # CRITICAL FIX: Merge incoming toc_progress with existing, don't replace
            # This preserves previous chapter completions when updating individual chapters
            merged_progress = existing_toc_progress.copy()
            merged_progress.update(parsed_toc_value)
            progress.toc_progress = merged_progress
            completed_count = sum(1 for v in merged_progress.values() if v)
            logger.info(f"📚 Updated toc_progress for book, now has {len(merged_progress)} entries, {completed_count} completed")
        else:
            # Fallback if types are not as expected
            progress.toc_progress = parsed_toc_value
            logger.warning(f"toc_progress update fallback used. Value: {parsed_toc_value}")

    def _update_progress_fields(self, progress: BookProgress, update_data: dict) -> None:
        """Update basic progress fields from update data."""
        for field, value in update_data.items():
            if field == "bookmarks" and value is not None:
                setattr(progress, field, json.dumps(value))
            elif field == "toc_progress" and value is not None:
                self._update_toc_progress(progress, value)
            else:
                setattr(progress, field, value)

    def _update_page_progress(self, progress: BookProgress, book: Book, progress_data: BookProgressUpdate) -> None:
        """Update page-based progress calculations."""
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

    async def update_book_progress(self, book_id: UUID, progress_data: BookProgressUpdate | None = None) -> BookProgressResponse:
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
        if progress_data is None:
            progress_data = BookProgressUpdate()

        start_time = datetime.now(UTC)
        logger.info(f"📚 [PERF] Starting book progress update for {book_id}")

        try:
            # OPTIMIZATION: Use single query to get book and progress together
            book_query = select(Book).where(Book.id == book_id).options(selectinload(Book.progress_records))
            book_result = await self.session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            query_time = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            logger.info(f"📚 [PERF] Book query took {query_time}ms")

            # Get or create progress record
            progress = await self._get_or_create_progress(book_id)

            # Update progress fields
            update_data = progress_data.model_dump(exclude_unset=True)
            self._update_progress_fields(progress, update_data)

            # Update page-based progress
            self._update_page_progress(progress, book, progress_data)

            # OPTIMIZATION: Only recalculate if toc_progress was updated
            if book.table_of_contents and "toc_progress" in update_data:
                calc_start = datetime.now(UTC)
                logger.info(f"📚 [PERF] Recalculating progress for book {book_id}")
                progress.progress_percentage = await self.get_book_toc_progress_percentage(book_id)
                calc_time = int((datetime.now(UTC) - calc_start).total_seconds() * 1000)
                logger.info(f"📚 [PERF] Progress calculation took {calc_time}ms, result: {progress.progress_percentage}%")
            elif progress.toc_progress:
                # If we have toc_progress but no ToC in book (shouldn't happen), log warning
                logger.warning(f"⚠️ Book {book_id} has toc_progress but no table_of_contents")

            progress.last_read_at = datetime.now(UTC)
            progress.updated_at = datetime.now(UTC)

            # OPTIMIZATION: Don't refresh if we don't need updated data
            commit_start = datetime.now(UTC)
            await self.session.commit()
            commit_time = int((datetime.now(UTC) - commit_start).total_seconds() * 1000)
            logger.info(f"📚 [PERF] Database commit took {commit_time}ms")

            # Create response without refresh
            response = BookProgressResponse.model_validate(progress)

            total_time = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
            logger.info(f"📚 [PERF] Total book progress update took {total_time}ms")

            return response

        except HTTPException:
            raise
        except Exception as e:
            logging.exception(f"Error updating book progress for {book_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update book progress: {e!s}",
            ) from e
