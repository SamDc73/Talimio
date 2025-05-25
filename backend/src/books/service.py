import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.session import async_session_maker

from .models import Book, BookProgress
from .schemas import (
    BookCreate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
)


DEFAULT_USER_ID = "default_user"  # For now, use default user
UPLOAD_DIR = Path("backend/uploads/books")
ALLOWED_EXTENSIONS = {".pdf", ".epub"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def _book_to_response(book: Book) -> BookResponse:
    """Convert Book model to BookResponse with proper tags handling."""
    tags_list = []
    if book.tags:
        try:
            tags_list = json.loads(book.tags)
        except (json.JSONDecodeError, TypeError):
            tags_list = []

    return BookResponse(
        id=book.id,
        title=book.title,
        subtitle=book.subtitle,
        author=book.author,
        description=book.description,
        isbn=book.isbn,
        language=book.language,
        publication_year=book.publication_year,
        publisher=book.publisher,
        tags=tags_list,
        file_type=book.file_type,
        file_size=book.file_size,
        total_pages=book.total_pages,
        cover_image_path=book.cover_image_path,
        created_at=book.created_at,
        updated_at=book.updated_at,
    )


async def create_book(book_data: BookCreate, file: UploadFile) -> BookResponse:
    """
    Create a new book with uploaded file.

    Args:
        book_data: Book creation data
        file: Uploaded book file

    Returns
    -------
        BookResponse: Created book data

    Raises
    ------
        HTTPException: If creation fails
    """
    try:
        # Validate file
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided",
            )

        file_extension = Path(file.filename).suffix.lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type {file_extension} not supported. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
            )

        # Check file size
        file_content = await file.read()
        if len(file_content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
            )

        # Create upload directory
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        from uuid import uuid4

        unique_filename = f"{uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / unique_filename

        # Save file
        file_path.write_bytes(file_content)

        # Create book record
        async with async_session_maker() as session:
            book = Book(
                title=book_data.title,
                subtitle=book_data.subtitle,
                author=book_data.author,
                description=book_data.description,
                isbn=book_data.isbn,
                file_path=str(file_path),
                file_type=book_data.file_type,
                file_size=len(file_content),
                language=book_data.language,
                publication_year=book_data.publication_year,
                publisher=book_data.publisher,
                tags=json.dumps(book_data.tags) if book_data.tags else None,
            )

            session.add(book)
            await session.commit()
            await session.refresh(book)

            return _book_to_response(book)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error creating book")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create book: {e!s}",
        ) from e


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
                books=book_responses,
                total=total,
                page=page,
                per_page=per_page,
            )

    except Exception as e:
        logging.exception("Error getting books")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get books: {e!s}",
        ) from e


async def get_book(book_id: UUID) -> BookWithProgress:
    """
    Get a book by ID with progress information.

    Args:
        book_id: Book ID

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

            # Get progress for default user
            progress = None
            for prog in book.progress_records:
                if prog.user_id == DEFAULT_USER_ID:
                    progress = BookProgressResponse.model_validate(prog)
                    break

            book_response = _book_to_response(book)
            return BookWithProgress(
                **book_response.model_dump(),
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
    Delete a book and its associated file.

    Args:
        book_id: Book ID

    Raises
    ------
        HTTPException: If book not found or deletion fails
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

            # Delete file if it exists
            try:
                file_path = Path(book.file_path)
                if file_path.exists():
                    file_path.unlink()
            except Exception as file_error:
                logging.warning(f"Failed to delete book file {book.file_path}: {file_error}")

            # Delete book record (progress records will be cascade deleted)
            await session.delete(book)
            await session.commit()

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error deleting book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete book: {e!s}",
        ) from e


async def update_book_progress(book_id: UUID, progress_data: BookProgressUpdate) -> BookProgressResponse:
    """
    Update reading progress for a book.

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
        async with async_session_maker() as session:
            # Check if book exists
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Find or create progress record
            progress_query = select(BookProgress).where(
                BookProgress.book_id == book_id,
                BookProgress.user_id == DEFAULT_USER_ID,
            )
            progress_result = await session.execute(progress_query)
            progress = progress_result.scalar_one_or_none()

            if not progress:
                progress = BookProgress(
                    book_id=book_id,
                    user_id=DEFAULT_USER_ID,
                )
                session.add(progress)

            # Update progress fields
            update_data = progress_data.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if field == "bookmarks" and value is not None:
                    setattr(progress, field, json.dumps(value))
                else:
                    setattr(progress, field, value)

            progress.last_read_at = datetime.now(UTC)
            progress.updated_at = datetime.now(UTC)

            # Calculate total pages read based on current page
            if progress_data.current_page is not None:
                progress.total_pages_read = max(progress.total_pages_read, progress_data.current_page)

            await session.commit()
            await session.refresh(progress)

            return BookProgressResponse.model_validate(progress)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error updating book progress for {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update book progress: {e!s}",
        ) from e
