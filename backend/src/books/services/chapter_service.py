"""Chapter service for book chapter management."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book, BookChapter
from src.books.schemas import BookChapterResponse
from src.books.services.book_response_builder import BookResponseBuilder


logger = logging.getLogger(__name__)


class ChapterService:
    """Service for managing book chapters."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the chapter service."""
        self.session = session

    async def get_book_chapters(self, book_id: UUID) -> list[BookChapterResponse]:
        """Get all chapters for a book."""
        # Verify book exists
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        # Get chapters
        chapters_query = select(BookChapter).where(BookChapter.book_id == book_id).order_by(BookChapter.chapter_number)
        chapters_result = await self.session.execute(chapters_query)
        chapters = chapters_result.scalars().all()

        return BookResponseBuilder.build_chapter_list(chapters)

    async def get_book_chapter(self, book_id: UUID, chapter_id: UUID) -> BookChapterResponse:
        """Get a specific chapter for a book."""
        # Verify book exists
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        # Get chapter
        chapter_query = select(BookChapter).where(
            BookChapter.id == chapter_id,
            BookChapter.book_id == book_id,
        )
        chapter_result = await self.session.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter {chapter_id} not found",
            )

        return BookResponseBuilder.build_chapter_response(chapter)

    async def update_chapter_status(
        self, book_id: UUID, chapter_id: UUID, chapter_status: str, user_id: UUID
    ) -> BookChapterResponse:
        """Update the status of a book chapter."""
        # Verify book exists
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        # Get chapter
        chapter_query = select(BookChapter).where(
            BookChapter.id == chapter_id,
            BookChapter.book_id == book_id,
        )
        chapter_result = await self.session.execute(chapter_query)
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapter {chapter_id} not found",
            )

        # Validate status
        valid_statuses = ["not_started", "in_progress", "completed"]
        if chapter_status not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status '{chapter_status}'. Valid statuses are: {', '.join(valid_statuses)}",
            )

        # Update chapter status
        chapter.status = chapter_status
        chapter.updated_at = datetime.now(UTC)

        # Update toc_progress in book_progress table
        from src.books.models import BookProgress

        progress_query = select(BookProgress).where(BookProgress.book_id == book_id, BookProgress.user_id == user_id)
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress:
            progress = BookProgress(book_id=book_id, user_id=user_id, toc_progress={})
            self.session.add(progress)

        if progress.toc_progress is None:
            progress.toc_progress = {}

        # Ensure toc_progress is a dict before using it
        if isinstance(progress.toc_progress, dict):
            progress.toc_progress[str(chapter_id)] = chapter_status == "completed"
        else:
            progress.toc_progress = {str(chapter_id): chapter_status == "completed"}
        progress.updated_at = datetime.now(UTC)

        # Update the overall book progress
        from src.books.services.book_progress_service import BookProgressService

        progress_service = BookProgressService()
        # Mark chapter as complete/incomplete in the service
        await progress_service.mark_chapter_complete(book_id, user_id, str(chapter_id), chapter_status == "completed")

        await self.session.commit()
        await self.session.refresh(chapter)
        await self.session.refresh(progress)

        return BookResponseBuilder.build_chapter_response(chapter)

    async def extract_and_create_chapters(self, book_id: UUID) -> list[BookChapterResponse]:
        """Extract chapters from book's table of contents and create chapter records."""
        # Get book with table of contents
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        if not book.table_of_contents:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Book has no table of contents",
            )

        # Parse table of contents
        try:
            toc_data = json.loads(book.table_of_contents)
        except (json.JSONDecodeError, TypeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid table of contents format",
            ) from e

        # Clear existing chapters
        delete_query = select(BookChapter).where(BookChapter.book_id == book_id)
        delete_result = await self.session.execute(delete_query)
        existing_chapters = delete_result.scalars().all()
        for chapter in existing_chapters:
            await self.session.delete(chapter)

        # Create chapters from TOC (top-level items only)
        chapters = []
        for i, item in enumerate(toc_data):
            if item.get("level", 0) == 0:  # Only top-level chapters
                chapter = BookChapter(
                    book_id=book_id,
                    chapter_number=i + 1,
                    title=item.get("title", f"Chapter {i + 1}"),
                    start_page=item.get("start_page") or item.get("page"),
                    end_page=item.get("end_page"),
                    status="not_started",
                )
                self.session.add(chapter)
                chapters.append(chapter)

        await self.session.commit()

        # Refresh chapters to get IDs
        for chapter in chapters:
            await self.session.refresh(chapter)

        return BookResponseBuilder.build_chapter_list(chapters)

    async def batch_update_chapter_statuses(
        self, book_id: UUID, updates: list[dict[str, str]]
    ) -> list[BookChapterResponse]:
        """Update multiple chapter statuses in one transaction."""
        # Verify book exists
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Book {book_id} not found",
            )

        updated_chapters = []
        chapter_ids = [UUID(update["chapter_id"]) for update in updates]

        # Get all chapters to update in one query
        chapters_query = select(BookChapter).where(BookChapter.book_id == book_id, BookChapter.id.in_(chapter_ids))
        chapters_result = await self.session.execute(chapters_query)
        chapters = {str(chapter.id): chapter for chapter in chapters_result.scalars().all()}

        # Verify all chapters exist
        missing_chapters = {update["chapter_id"] for update in updates} - set(chapters.keys())
        if missing_chapters:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Chapters not found: {', '.join(missing_chapters)}",
            )

        # Update chapters
        for update in updates:
            chapter_id_str = update["chapter_id"]
            new_status = update["status"]

            chapter = chapters[chapter_id_str]
            chapter.status = new_status
            chapter.updated_at = datetime.now(UTC)

            updated_chapters.append(chapter)

        await self.session.commit()

        # Refresh chapters to get updated timestamps
        for chapter in updated_chapters:
            await self.session.refresh(chapter)

        return BookResponseBuilder.build_chapter_list(updated_chapters)

    async def get_next_chapter(self, book_id: UUID, current_chapter_id: UUID) -> BookChapterResponse | None:
        """Get the next chapter in reading order."""
        # Get current chapter
        current_chapter_query = select(BookChapter).where(
            BookChapter.id == current_chapter_id,
            BookChapter.book_id == book_id,
        )
        current_result = await self.session.execute(current_chapter_query)
        current_chapter = current_result.scalar_one_or_none()

        if not current_chapter:
            return None

        # Get next chapter by chapter number
        next_chapter_query = (
            select(BookChapter)
            .where(
                BookChapter.book_id == book_id,
                BookChapter.chapter_number > current_chapter.chapter_number,
            )
            .order_by(BookChapter.chapter_number)
            .limit(1)
        )

        next_result = await self.session.execute(next_chapter_query)
        next_chapter = next_result.scalar_one_or_none()

        return BookResponseBuilder.build_chapter_response(next_chapter) if next_chapter else None

    async def get_previous_chapter(self, book_id: UUID, current_chapter_id: UUID) -> BookChapterResponse | None:
        """Get the previous chapter in reading order."""
        # Get current chapter
        current_chapter_query = select(BookChapter).where(
            BookChapter.id == current_chapter_id,
            BookChapter.book_id == book_id,
        )
        current_result = await self.session.execute(current_chapter_query)
        current_chapter = current_result.scalar_one_or_none()

        if not current_chapter:
            return None

        # Get previous chapter by chapter number
        prev_chapter_query = (
            select(BookChapter)
            .where(
                BookChapter.book_id == book_id,
                BookChapter.chapter_number < current_chapter.chapter_number,
            )
            .order_by(BookChapter.chapter_number.desc())
            .limit(1)
        )

        prev_result = await self.session.execute(prev_chapter_query)
        prev_chapter = prev_result.scalar_one_or_none()

        return BookResponseBuilder.build_chapter_response(prev_chapter) if prev_chapter else None

    async def get_chapter_by_number(self, book_id: UUID, chapter_number: int) -> BookChapterResponse | None:
        """Get a chapter by its number."""
        chapter_query = select(BookChapter).where(
            BookChapter.book_id == book_id,
            BookChapter.chapter_number == chapter_number,
        )
        result = await self.session.execute(chapter_query)
        chapter = result.scalar_one_or_none()

        return BookResponseBuilder.build_chapter_response(chapter) if chapter else None

    async def get_chapters_by_status(self, book_id: UUID, status: str) -> list[BookChapterResponse]:
        """Get chapters by their status."""
        chapters_query = (
            select(BookChapter)
            .where(
                BookChapter.book_id == book_id,
                BookChapter.status == status,
            )
            .order_by(BookChapter.chapter_number)
        )

        result = await self.session.execute(chapters_query)
        chapters = result.scalars().all()

        return BookResponseBuilder.build_chapter_list(chapters)
