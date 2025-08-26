"""Book progress service for tracking reading progress.

Provides progress tracking for books with TOC-based calculation logic.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.books.models import Book
from src.database.session import async_session_maker
from src.progress.models import ProgressUpdate
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


class BookProgressService:
    """Progress service for books with progress tracking functionality."""

    async def initialize_progress(self, content_id: UUID, user_id: UUID, total_pages: int = 0) -> None:
        """Initialize progress tracking for a new book."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)

            metadata = {"current_page": 1, "total_pages": total_pages, "toc_progress": {}, "bookmarks": []}
            progress_update = ProgressUpdate(progress_percentage=0, metadata=metadata)

            await progress_service.update_progress(
                user_id=user_id, content_id=content_id, content_type="book", progress=progress_update
            )

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific book and user."""
        async with async_session_maker() as session:
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
                        content_id, user_id, session, book, toc_progress
                    )
                except Exception as e:
                    logger.warning(f"Failed to calculate book progress percentage: {e}")
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
                book_query = select(Book).where(Book.id == content_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if book and book.total_pages > 0:
                    page_based_percentage = (progress_data["page"] / book.total_pages) * 100
                    completion_percentage = min(page_based_percentage, 100.0)

            if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
                completion_percentage = progress_data["completion_percentage"]

            if "toc_progress" in progress_data:
                # CRITICAL FIX: Merge incoming toc_progress with existing, don't replace
                existing_toc_progress = metadata.get("toc_progress", {})
                if isinstance(existing_toc_progress, dict) and isinstance(progress_data["toc_progress"], dict):
                    merged_progress = existing_toc_progress.copy()
                    merged_progress.update(progress_data["toc_progress"])
                    metadata["toc_progress"] = merged_progress
                else:
                    metadata["toc_progress"] = progress_data["toc_progress"]

                # Recalculate completion percentage after TOC updates
                book_query = select(Book).where(Book.id == content_id)
                book_result = await session.execute(book_query)
                book = book_result.scalar_one_or_none()

                if book and book.table_of_contents and metadata["toc_progress"]:
                    try:
                        completion_percentage = await self.get_book_toc_progress_percentage(
                            content_id, user_id, session, book, metadata["toc_progress"]
                        )
                    except Exception as e:
                        logger.warning(f"Failed to recalculate book progress percentage: {e}")

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

            # Get book for recalculation
            book_query = select(Book).where(Book.id == content_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            # Recalculate completion percentage
            completion_percentage = 0
            if book and book.table_of_contents:
                try:
                    completion_percentage = await self.get_book_toc_progress_percentage(
                        content_id, user_id, session, book, toc_progress
                    )
                except Exception as e:
                    logger.warning(f"Failed to recalculate book progress percentage: {e}")
                    completion_percentage = current_progress.progress_percentage if current_progress else 0

            # Update progress
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)
            await progress_service.update_progress(user_id, content_id, "book", progress_update)

    # TOC Progress Calculation Methods

    async def get_book_toc_progress_percentage(
        self, book_id: UUID, user_id: UUID, session: Any = None, book: Any = None, toc_progress: dict | None = None
    ) -> int:
        """Calculate book progress based on completed leaf sections.

        Returns percentage (0-100) based on completed leaf sections.
        """
        start_time = datetime.now(UTC)

        # If session not provided, create one
        if session is None:
            async with async_session_maker() as new_session:
                return await self.get_book_toc_progress_percentage(book_id, user_id, new_session, book, toc_progress)

        # Get book and progress data if not provided
        if book is None or toc_progress is None:
            # For new unified progress service, we get toc_progress from metadata
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, book_id)

            if not progress_data or not progress_data.metadata:
                return 0

            toc_progress = progress_data.metadata.get("toc_progress", {})

            # Get book with TOC
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book or not book.table_of_contents:
                return 0

        # Calculate progress percentage
        percentage = self._calculate_toc_percentage(book, toc_progress)

        elapsed_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)
        logger.info(f"📚 Book {book_id} progress calculation took {elapsed_ms}ms")

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

        percentage = int((completed_sections / total_sections) * 100)
        logger.info(f"📚 Book progress: {completed_sections}/{total_sections} sections = {percentage}%")
        return percentage

    async def get_toc_completion_stats(self, book_id: UUID, user_id: UUID) -> dict:
        """Get detailed TOC completion statistics.

        Returns both section-based and page-based progress metrics.
        """
        async with async_session_maker() as session:
            # Get book with TOC
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book or not book.table_of_contents:
                return {
                    "total_sections": 0,
                    "completed_sections": 0,
                    "section_percentage": 0,
                    "page_percentage": 0,
                    "completed_pages": 0,
                    "total_pages": 0,
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
                    "total_pages": 0,
                }

            # Get progress from unified service
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, book_id)
            toc_progress = progress_data.metadata.get("toc_progress", {}) if progress_data and progress_data.metadata else {}

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
                "total_pages": total_pages,
            }

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
                if toc_progress.get(str(item.get("id")), False):
                    completed += 1

                # Recursively count children
                if item.get("children"):
                    count_sections(item["children"])

        if isinstance(toc_items, list):
            count_sections(toc_items)
        else:
            count_sections([toc_items])

        return total, completed

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
        completed_pages = self._process_toc_chapters(items_to_process, toc_progress, total_pages, processed_page_ranges)

        progress = int((completed_pages / total_pages) * 100)
        logger.info(f"Chapter-weighted progress: {completed_pages}/{total_pages} pages = {progress}%")
        return min(progress, 100)  # Cap at 100%

    def _process_toc_chapters(
        self,
        items: list[dict],
        toc_progress: dict,
        total_pages: int,
        processed_ranges: list[tuple[int, int]],
        parent_completed: bool = False,
    ) -> int:
        """Process TOC chapters and calculate completed pages."""
        completed_pages = 0

        for i, item in enumerate(items):
            item_id = str(item.get("id"))

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

