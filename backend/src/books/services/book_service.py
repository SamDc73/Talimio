"""Core book service for basic CRUD operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.books.models import Book, BookChapter, BookProgress
from src.books.schemas import (
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
    TableOfContentsItem,
)
from src.config.settings import DEFAULT_USER_ID
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


def _book_to_response(book: Book) -> BookResponse:
    """Convert Book model to BookResponse with proper tags handling."""
    # Extract all attributes while we have them loaded
    book_id = book.id
    title = book.title
    subtitle = book.subtitle
    author = book.author
    description = book.description
    isbn = book.isbn
    language = book.language
    publication_year = book.publication_year
    publisher = book.publisher
    file_path = book.file_path
    file_type = book.file_type
    file_size = book.file_size
    total_pages = book.total_pages
    cover_image_path = book.cover_image_path
    created_at = book.created_at
    updated_at = book.updated_at

    tags_list = []
    if book.tags:
        try:
            tags_list = json.loads(book.tags)  # type: ignore[arg-type]
        except (json.JSONDecodeError, TypeError):
            tags_list = []

    # Handle table of contents
    toc_list = None
    if book.table_of_contents:
        try:
            toc_data = json.loads(book.table_of_contents)  # type: ignore[arg-type]
            if isinstance(toc_data, list):
                toc_list = _convert_toc_to_schema(toc_data)
        except (json.JSONDecodeError, TypeError):
            toc_list = None

    return BookResponse(
        id=book_id,
        title=title,
        subtitle=subtitle,
        author=author,
        description=description,
        isbn=isbn,
        language=language,
        publication_year=publication_year,
        publisher=publisher,
        tags=tags_list,
        file_path=file_path,
        file_type=file_type,
        file_size=file_size,
        total_pages=total_pages,
        cover_image_path=cover_image_path,
        table_of_contents=toc_list,
        created_at=created_at,
        updated_at=updated_at,
    )


def _convert_toc_to_schema(toc_data: list[dict]) -> list[TableOfContentsItem]:
    """Convert table of contents data to schema objects."""
    result = []
    for item in toc_data:
        children = []
        if item.get("children"):
            children = _convert_toc_to_schema(item["children"])

        toc_item = TableOfContentsItem(
            id=item.get("id", ""),
            title=item.get("title", ""),
            page=item.get("page"),
            start_page=item.get("start_page"),
            end_page=item.get("end_page"),
            level=item.get("level", 0),
            children=children,
        )
        result.append(toc_item)
    return result



async def get_books(page: int = 1, per_page: int = 20) -> BookListResponse:
    """
    Get list of books with pagination.

    Args:
        page: Page number (1-based)
        per_page: Number of books per page

    Returns
    -------
        BookListResponse: List of books with pagination info

    Raises
    ------
        HTTPException: If retrieval fails
    """
    try:
        async with async_session_maker() as session:
            # Get total count
            count_query = select(Book)
            total_result = await session.execute(count_query)
            total = len(total_result.all())

            # Get paginated books
            offset = (page - 1) * per_page
            query = select(Book).offset(offset).limit(per_page)
            result = await session.execute(query)
            books = result.scalars().all()

            book_responses = [_book_to_response(book) for book in books]

            return BookListResponse(
                items=book_responses,
                total=total,
                page=page,
                pages=(total + per_page - 1) // per_page,
            )

    except Exception as e:
        logging.exception("Error getting books")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get books: {e!s}",
        ) from e


async def get_book(book_id: UUID, user_id: UUID | None = None) -> BookWithProgress:
    """
    Get a book by ID with progress information.

    Args:
        book_id: Book ID
        user_id: User ID for fetching user-specific progress

    Returns
    -------
        BookWithProgress: Book data with progress

    Raises
    ------
        HTTPException: If book not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:
            query = select(Book).options(selectinload(Book.progress_records)).where(Book.id == book_id)
            result = await session.execute(query)
            book = result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Get progress for current user
            progress = None
            if user_id:
                for prog in book.progress_records:
                    if prog.user_id == user_id:
                        progress = BookProgressResponse.model_validate(prog)
                        break
            else:
                # Fallback to default user for backward compatibility
                for prog in book.progress_records:
                    if prog.user_id == DEFAULT_USER_ID:
                        progress = BookProgressResponse.model_validate(prog)
                        break

            book_response = _book_to_response(book)
            return BookWithProgress(
                id=book_response.id,
                title=book_response.title,
                subtitle=book_response.subtitle,
                author=book_response.author,
                description=book_response.description,
                isbn=book_response.isbn,
                language=book_response.language,
                publication_year=book_response.publication_year,
                publisher=book_response.publisher,
                tags=book_response.tags,
                file_path=book_response.file_path,
                file_type=book_response.file_type,
                file_size=book_response.file_size,
                total_pages=book_response.total_pages,
                cover_image_path=book_response.cover_image_path,
                table_of_contents=book_response.table_of_contents,
                created_at=book_response.created_at,
                updated_at=book_response.updated_at,
                progress=progress,
            )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error getting book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get book: {e!s}",
        ) from e


async def update_book(book_id: UUID, book_data: BookUpdate) -> BookResponse:
    """
    Update a book.

    Args:
        book_id: Book ID
        book_data: Updated book data

    Returns
    -------
        BookResponse: Updated book data

    Raises
    ------
        HTTPException: If book not found or update fails
    """
    try:
        async with async_session_maker() as session:
            query = select(Book).where(Book.id == book_id)
            result = await session.execute(query)
            book = result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Update fields
            update_data = book_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "tags" and value is not None:
                    setattr(book, field, json.dumps(value))
                else:
                    setattr(book, field, value)

            book.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(book)

            return _book_to_response(book)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error updating book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update book: {e!s}",
        ) from e


async def delete_book(book_id: UUID) -> None:
    """
    Delete a book by ID.

    Args:
        book_id: Book ID

    Raises
    ------
        HTTPException: If book not found or deletion fails
    """
    try:
        async with async_session_maker() as session:
            # Check if book exists first
            query = select(Book).where(Book.id == book_id)
            result = await session.execute(query)
            book = result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Delete dependent records first to avoid FK constraint violations
            # 1. Delete book progress records
            from src.books.models import BookChapter, BookProgress
            await session.execute(delete(BookProgress).where(BookProgress.book_id == book_id))

            # 2. Delete book chapters (these should CASCADE but be explicit)
            await session.execute(delete(BookChapter).where(BookChapter.book_id == book_id))

            # 3. Finally delete the book
            delete_query = delete(Book).where(Book.id == book_id)
            await session.execute(delete_query)
            await session.commit()

            logger.info(f"Successfully deleted book {book_id}")

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error deleting book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete book: {e!s}",
        ) from e


class BookService:
    """Service for managing book progress and operations."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the book service."""
        self.session = session

    async def get_book_progress(self, book_id: UUID) -> int:
        """Calculate book progress based on completed chapters.

        Returns percentage (0-100) of completed chapters.
        This matches the ProgressCalculator interface.
        """
        from sqlalchemy import func

        # Count total and completed chapters
        stats_query = select(
            func.count(BookChapter.id).label("total"),
            func.count(BookChapter.id).filter(BookChapter.status == "completed").label("completed"),
        ).where(BookChapter.book_id == book_id)

        result = await self.session.execute(stats_query)
        stats = result.first()

        if not stats or stats.total == 0:
            # Fallback to page-based progress if no chapters
            query = (
                select(BookProgress.progress_percentage)
                .where(BookProgress.book_id == book_id)
                .order_by(BookProgress.updated_at.desc())
                .limit(1)
            )
            result = await self.session.execute(query)
            progress = result.scalar()
            return int(progress or 0)

        return int((stats.completed / stats.total) * 100)

    async def get_chapter_completion_stats(self, book_id: UUID) -> dict:
        """Get detailed chapter completion statistics.

        Returns statistics about chapter completion for the book.
        """
        from sqlalchemy import func

        # Count total and completed chapters
        stats_query = select(
            func.count(BookChapter.id).label("total"),
            func.count(BookChapter.id).filter(BookChapter.status == "completed").label("completed"),
            func.count(BookChapter.id).filter(BookChapter.status == "in_progress").label("in_progress"),
        ).where(BookChapter.book_id == book_id)

        result = await self.session.execute(stats_query)
        stats = result.first()

        if not stats or stats.total == 0:
            # Fallback to page-based progress if no chapters
            query = (
                select(BookProgress.progress_percentage)
                .where(BookProgress.book_id == book_id)
                .order_by(BookProgress.updated_at.desc())
                .limit(1)
            )
            result = await self.session.execute(query)
            progress = result.scalar() or 0

            return {
                "total_chapters": 0,
                "completed_chapters": 0,
                "in_progress_chapters": 0,
                "not_started_chapters": 0,
                "completion_percentage": int(progress),
                "uses_page_based_progress": True,
            }

        completed_chapters = stats.completed
        in_progress_chapters = stats.in_progress
        not_started_chapters = stats.total - completed_chapters - in_progress_chapters

        return {
            "total_chapters": stats.total,
            "completed_chapters": completed_chapters,
            "in_progress_chapters": in_progress_chapters,
            "not_started_chapters": not_started_chapters,
            "completion_percentage": int((completed_chapters / stats.total) * 100) if stats.total > 0 else 0,
            "uses_page_based_progress": False,
        }


# Wrapper functions for backward compatibility with router imports
async def create_book(book_data, file, background_tasks):
    """Create a new book with uploaded file."""
    from src.books.services.book_upload_service import BookUploadService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        upload_service = BookUploadService(session)
        return await upload_service.create_book(book_data, file, background_tasks)


async def extract_and_update_toc(book_id: UUID):
    """Extract and update table of contents for an existing book."""
    from src.books.services.book_metadata_service import BookMetadataService
    from src.database.session import async_session_maker

    async with async_session_maker():
        metadata_service = BookMetadataService()
        return await metadata_service.extract_and_update_toc(book_id)


async def get_book_chapters(book_id: UUID):
    """Get all chapters for a book."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.get_book_chapters(book_id)


async def get_book_chapter(book_id: UUID, chapter_id: UUID):
    """Get a specific chapter for a book."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.get_book_chapter(book_id, chapter_id)


async def update_book_chapter_status(book_id: UUID, chapter_id: UUID, chapter_status: str):
    """Update the status of a book chapter."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.update_chapter_status(book_id, chapter_id, chapter_status)


async def extract_and_create_chapters(book_id: UUID):
    """Extract chapters from book's table of contents and create chapter records."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.extract_and_create_chapters(book_id)


async def batch_update_chapter_statuses(book_id: UUID, updates: list):
    """Update multiple chapter statuses in one transaction."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.batch_update_chapter_statuses(book_id, updates)


async def update_book_progress(book_id: UUID, progress_data: BookProgressUpdate, user_id: UUID) -> BookProgressResponse:
    """Update reading progress for a book."""
    from src.books.services.book_progress_service import BookProgressService

    async with async_session_maker() as session:
        progress_service = BookProgressService(session, user_id)
        return await progress_service.update_book_progress(book_id, progress_data)
