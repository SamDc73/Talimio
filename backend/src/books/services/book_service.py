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
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class QueryBuilder:
    """Builds database queries with consistent filtering."""

    def apply_user_filter(self, query: select, user_id: UUID) -> select:
        """Apply user ownership filter to a query."""
        return query.where(Book.user_id == user_id)

    def validate_user_ownership(self, book: Book, user_id: UUID) -> bool:
        """Validate if the user owns the book."""
        return book.user_id == user_id


# Create a single instance to use throughout the module
query_builder = QueryBuilder()


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
    rag_status = book.rag_status
    rag_processed_at = book.rag_processed_at
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
        table_of_contents=toc_list,
        rag_status=rag_status,
        rag_processed_at=rag_processed_at,
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


async def get_books(user_id: UUID, page: int = 1, per_page: int = 20) -> BookListResponse:
    """
    Get list of books with pagination, filtered by user ownership.

    Args:
        user_id: User ID for filtering books
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
            # Build base query with user filtering
            base_query = select(Book)

            # Get total count
            count_query = select(Book)
            count_filtered_query = query_builder.apply_user_filter(count_query, user_id)
            total_result = await session.execute(count_filtered_query)
            total = len(total_result.all())

            # Get paginated books
            offset = (page - 1) * per_page
            paginated_query = base_query.offset(offset).limit(per_page).order_by(Book.updated_at.desc())
            result = await session.execute(paginated_query)
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


async def get_book(book_id: UUID, user_id: UUID) -> BookWithProgress:
    """
    Get a book by ID with progress information.

    Args:
        book_id: Book ID
        user_id: User ID for filtering books

    Returns
    -------
        BookWithProgress: Book data with progress

    Raises
    ------
        HTTPException: If book not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:

            # Build query with user filtering and book ID
            base_query = select(Book).options(selectinload(Book.progress_records)).where(Book.id == book_id)
            filtered_query = query_builder.apply_user_filter(base_query, user_id)

            result = await session.execute(filtered_query)
            book = result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Validate user ownership (important for multi-user mode)
            if not query_builder.validate_user_ownership(book, user_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Get progress for current user
            progress = None
            for prog in book.progress_records:
                if prog.user_id == user_id:
                    progress = BookProgressResponse.model_validate(prog)
                    break

            book_response = _book_to_response(book)
            return BookWithProgress(**book_response.model_dump(), progress=progress)

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
                if (field == "tags" and value is not None) or (field == "table_of_contents" and value is not None):
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


async def delete_book(book_id: UUID, user_id: UUID | None = None, session: AsyncSession | None = None) -> None:
    """
    Delete a book by ID with optional user filtering.

    Args:
        book_id: Book ID
        user_id: Optional user ID for ownership validation
        session: Optional database session (if not provided, creates a new one)

    Raises
    ------
        HTTPException: If book not found or deletion fails
    """
    try:

        async def _delete_book_logic(db_session: AsyncSession) -> None:

            # Build query with user filtering if user_id provided
            base_query = select(Book).where(Book.id == book_id)
            filtered_query = query_builder.apply_user_filter(base_query, user_id) if user_id else base_query

            result = await db_session.execute(filtered_query)
            book = result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Validate user ownership if user_id provided
            if user_id and not query_builder.validate_user_ownership(book, user_id):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Delete dependent records first to avoid FK constraint violations
            # 1. Delete book progress records
            from src.books.models import BookChapter, BookProgress

            await db_session.execute(delete(BookProgress).where(BookProgress.book_id == book_id))

            # 2. Delete book chapters (these should CASCADE but be explicit)
            await db_session.execute(delete(BookChapter).where(BookChapter.book_id == book_id))

            # 3. Finally delete the book
            delete_query = delete(Book).where(Book.id == book_id)
            await db_session.execute(delete_query)
            await db_session.commit()

            logger.info(f"Successfully deleted book {book_id}")

        # Use provided session or create a new one
        if session:
            await _delete_book_logic(session)
        else:
            async with async_session_maker() as new_session:
                await _delete_book_logic(new_session)

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

    async def get_book(self, book_id: UUID) -> Book | None:
        """Get a book by ID.

        Args:
            book_id: ID of the book to retrieve

        Returns
        -------
            Book object or None if not found
        """
        query = select(Book).where(Book.id == book_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_books(self, user_id: UUID) -> list[Book]:
        """Get all books for a user.

        Args:
            user_id: User ID to filter books

        Returns
        -------
            List of Book objects
        """
        query = select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_book_progress(self, book_id: UUID, user_id: UUID) -> int:
        """Calculate book progress based on current page and total pages.

        Returns percentage (0-100) based on page-based progress.
        This matches the ProgressCalculator interface and provides simple page-based progress.

        Args:
            book_id: ID of the book to get progress for
            user_id: User ID for filtering books
        """
        from src.books.models import BookProgress

        # Get the book to get total pages
        book_query = select(Book).where(Book.id == book_id)
        book_result = await self.session.execute(book_query)
        book = book_result.scalar_one_or_none()

        if not book or not book.total_pages:
            return 0

        # Get progress record for page-based calculation
        progress_query = select(BookProgress).where(BookProgress.book_id == book_id, BookProgress.user_id == user_id)
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress or not progress.current_page:
            return 0

        # Calculate page-based progress percentage
        progress_percentage = min(100, (progress.current_page / book.total_pages) * 100)
        return int(progress_percentage)

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
async def create_book(book_data: dict, file: object, background_tasks: object, user_id: UUID) -> dict:
    """Create a new book with uploaded file."""
    from src.books.services.book_upload_service import BookUploadService
    from src.database.session import async_session_maker


    async with async_session_maker() as session:
        upload_service = BookUploadService(session)
        return await upload_service.create_book(book_data, file, background_tasks, user_id)


async def extract_and_update_toc(book_id: UUID, user_id: UUID) -> BookResponse:
    """Extract and update table of contents for an existing book."""
    import httpx

    from src.books.services.book_metadata_service import BookMetadataService
    from src.database.session import async_session_maker
    from src.storage.factory import get_storage_provider

    async with async_session_maker():
        # 1. Get the book to find its file path
        book = await get_book(book_id, user_id)
        if not book or not book.file_path:
            raise HTTPException(status_code=404, detail="Book or book file not found")

        # 2. Get a download URL and fetch the file content
        storage = get_storage_provider()
        download_url = await storage.get_download_url(book.file_path)
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)
            response.raise_for_status()  # Raise an exception for bad status codes
            file_content = response.content

        # 3. Extract metadata
        metadata_service = BookMetadataService()
        metadata = metadata_service.extract_metadata(file_content, f".{book.file_type}")

        # 4. Update the book with the new table of contents
        if metadata.table_of_contents:
            book_update = BookUpdate(table_of_contents=json.dumps(metadata.table_of_contents))
            return await update_book(book_id, book_update)
        return _book_to_response(book)


async def get_book_chapters(book_id: UUID) -> list:
    """Get all chapters for a book."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.get_book_chapters(book_id)


async def get_book_chapter(book_id: UUID, chapter_id: UUID) -> dict:
    """Get a specific chapter for a book."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.get_book_chapter(book_id, chapter_id)


async def update_book_chapter_status(book_id: UUID, chapter_id: UUID, chapter_status: str) -> dict:
    """Update the status of a book chapter."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.update_chapter_status(book_id, chapter_id, chapter_status)


async def extract_and_create_chapters(book_id: UUID) -> list:
    """Extract chapters from book's table of contents and create chapter records."""
    from src.books.services.chapter_service import ChapterService
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        chapter_service = ChapterService(session)
        return await chapter_service.extract_and_create_chapters(book_id)


async def batch_update_chapter_statuses(book_id: UUID, updates: list) -> None:
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
