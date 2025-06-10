import hashlib
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.session import async_session_maker


if TYPE_CHECKING:
    from src.books.metadata import BookMetadata

from .models import Book, BookChapter, BookProgress
from .schemas import (
    BookChapterResponse,
    BookCreate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
    TableOfContentsItem,
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
        file_path=book.file_path,
        file_type=book.file_type,
        file_size=book.file_size,
        total_pages=book.total_pages,
        cover_image_path=book.cover_image_path,
        table_of_contents=toc_list,
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
        file_content, file_extension, file_hash = await _validate_and_process_file(file)
        await _check_duplicate_book(file_hash)
        file_path = _save_file_to_disk(file_content, file_extension)
        metadata = _extract_file_metadata(file_content, file_extension)

        async with async_session_maker() as session:
            book = _create_book_record(book_data, file_path, file_content, file_hash, metadata)
            session.add(book)
            await session.commit()
            await session.refresh(book)

            await _apply_automatic_tagging(session, book, metadata)
            return _book_to_response(book)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error creating book")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create book: {e!s}",
        ) from e


async def _validate_and_process_file(file: UploadFile) -> tuple[bytes, str, str]:
    """Validate file and return content, extension, and hash."""
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

    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    file_hash = hashlib.sha256(file_content).hexdigest()
    return file_content, file_extension, file_hash


async def _check_duplicate_book(file_hash: str) -> None:
    """Check for duplicate books by file hash."""
    async with async_session_maker() as session:
        existing_book = await session.execute(
            select(Book).where(Book.file_hash == file_hash),
        )
        existing_book = existing_book.scalar_one_or_none()

        if existing_book:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This PDF already exists in the library as '{existing_book.title}' by {existing_book.author}",
            )


def _save_file_to_disk(file_content: bytes, file_extension: str) -> Path:
    """Save file to disk and return path."""
    from uuid import uuid4

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique_filename = f"{uuid4()}{file_extension}"
    file_path = UPLOAD_DIR / unique_filename
    file_path.write_bytes(file_content)
    return file_path


def _extract_file_metadata(file_content: bytes, file_extension: str) -> "BookMetadata":
    """Extract metadata from file content."""
    from .metadata import extract_metadata

    return extract_metadata(file_content, file_extension)


def _create_book_record(
    book_data: BookCreate,
    file_path: Path,
    file_content: bytes,
    file_hash: str,
    metadata: "BookMetadata",
) -> Book:
    """Create book database record."""
    return Book(
        title=book_data.title,
        subtitle=book_data.subtitle,
        author=book_data.author,
        description=book_data.description,
        isbn=book_data.isbn,
        file_path=str(file_path),
        file_type=book_data.file_type,
        file_size=len(file_content),
        file_hash=file_hash,
        language=book_data.language,
        publication_year=book_data.publication_year,
        publisher=book_data.publisher,
        tags=json.dumps(book_data.tags) if book_data.tags else None,
        total_pages=metadata.page_count,
        table_of_contents=json.dumps(metadata.table_of_contents) if metadata.table_of_contents else None,
    )


async def _apply_automatic_tagging(session: AsyncSession, book: Book, metadata: "BookMetadata") -> None:
    """Apply automatic tagging to the book."""
    try:
        from src.ai.client import ModelManager
        from src.tagging.service import TaggingService

        model_manager = ModelManager()
        tagging_service = TaggingService(session, model_manager)

        content_preview = _build_content_preview(book, metadata)
        tags = await tagging_service.tag_content(
            content_id=book.id,
            content_type="book",
            title=f"{book.title} {book.subtitle or ''}".strip(),
            content_preview="\n".join(content_preview),
        )

        if tags:
            book.tags = json.dumps(tags)
            await session.commit()

        logging.info(f"Successfully tagged book {book.id} with tags: {tags}")

    except Exception as e:
        logging.exception(f"Failed to tag book {book.id}: {e}")


def _build_content_preview(book: Book, metadata: "BookMetadata") -> list[str]:
    """Build content preview for tagging."""
    content_preview = []
    if book.description:
        content_preview.append(f"Description: {book.description}")

    if metadata.table_of_contents:
        toc_list = metadata.table_of_contents
        if toc_list and len(toc_list) > 0:
            toc_items = [item.get("title", "") for item in toc_list[:10]]
            if toc_items:
                content_preview.append(f"Table of Contents: {', '.join(toc_items)}")

    return content_preview


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
            if progress_data.current_page is not None and progress is not None:
                current_total = progress.total_pages_read if progress.total_pages_read is not None else 0
                progress.total_pages_read = max(current_total, progress_data.current_page)  # type: ignore[assignment]

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


async def extract_and_update_toc(book_id: UUID) -> BookResponse:
    """
    Extract and update table of contents for an existing book.

    Args:
        book_id: Book ID

    Returns
    -------
        BookResponse: Updated book data with table of contents

    Raises
    ------
        HTTPException: If book not found or extraction fails
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

            # Read the book file
            file_path = Path(book.file_path)
            if not file_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Book file not found on disk",
                )

            file_content = file_path.read_bytes()
            file_extension = f".{book.file_type}"

            # Extract metadata including table of contents
            from .metadata import extract_metadata

            metadata = extract_metadata(file_content, file_extension)

            # Update book with table of contents
            if metadata.table_of_contents:
                book.table_of_contents = json.dumps(metadata.table_of_contents)
                book.updated_at = datetime.now(UTC)

                await session.commit()
                await session.refresh(book)

            return _book_to_response(book)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error extracting TOC for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract table of contents: {e!s}",
        ) from e


# Phase 2.2: Book Chapter Methods
async def get_book_chapters(book_id: UUID) -> list[BookChapterResponse]:
    """
    Get all chapters for a book.

    Args:
        book_id: Book ID

    Returns
    -------
        list[BookChapterResponse]: List of book chapters

    Raises
    ------
        HTTPException: If book not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:
            # Verify book exists
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
            book = book_result.scalar_one_or_none()

            if not book:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Book {book_id} not found",
                )

            # Get chapters
            chapters_query = (
                select(BookChapter).where(BookChapter.book_id == book_id).order_by(BookChapter.chapter_number)
            )
            chapters_result = await session.execute(chapters_query)
            chapters = chapters_result.scalars().all()

            return [BookChapterResponse.model_validate(chapter) for chapter in chapters]

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error getting chapters for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get book chapters: {e!s}",
        ) from e


async def get_book_chapter(book_id: UUID, chapter_id: UUID) -> BookChapterResponse:
    """
    Get a specific chapter for a book.

    Args:
        book_id: Book ID
        chapter_id: Chapter ID

    Returns
    -------
        BookChapterResponse: Book chapter data

    Raises
    ------
        HTTPException: If book or chapter not found or retrieval fails
    """
    try:
        async with async_session_maker() as session:
            # Verify book exists
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
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
            chapter_result = await session.execute(chapter_query)
            chapter = chapter_result.scalar_one_or_none()

            if not chapter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chapter {chapter_id} not found",
                )

            return BookChapterResponse.model_validate(chapter)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error getting chapter {chapter_id} for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get book chapter: {e!s}",
        ) from e


async def update_book_chapter_status(book_id: UUID, chapter_id: UUID, chapter_status: str) -> BookChapterResponse:
    """
    Update the status of a book chapter.

    Args:
        book_id: Book ID
        chapter_id: Chapter ID
        chapter_status: New status

    Returns
    -------
        BookChapterResponse: Updated chapter data

    Raises
    ------
        HTTPException: If book or chapter not found or update fails
    """
    try:
        async with async_session_maker() as session:
            # Verify book exists
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
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
            chapter_result = await session.execute(chapter_query)
            chapter = chapter_result.scalar_one_or_none()

            if not chapter:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Chapter {chapter_id} not found",
                )

            # Validate status
            valid_statuses = ["not_started", "in_progress", "done"]
            if chapter_status not in valid_statuses:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status '{chapter_status}'. Valid statuses are: {', '.join(valid_statuses)}",
                )

            # Update status
            chapter.status = chapter_status
            chapter.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(chapter)

            return BookChapterResponse.model_validate(chapter)

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error updating chapter {chapter_id} status for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update chapter status: {e!s}",
        ) from e


async def extract_and_create_chapters(book_id: UUID) -> list[BookChapterResponse]:
    """
    Extract chapters from book's table of contents and create chapter records.

    Args:
        book_id: Book ID

    Returns
    -------
        list[BookChapterResponse]: Created chapters

    Raises
    ------
        HTTPException: If book not found or extraction fails
    """
    try:
        async with async_session_maker() as session:
            # Get book with table of contents
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
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
            import json

            try:
                toc_data = json.loads(book.table_of_contents)
            except (json.JSONDecodeError, TypeError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid table of contents format",
                ) from e

            # Clear existing chapters
            delete_query = select(BookChapter).where(BookChapter.book_id == book_id)
            delete_result = await session.execute(delete_query)
            existing_chapters = delete_result.scalars().all()
            for chapter in existing_chapters:
                await session.delete(chapter)

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
                    session.add(chapter)
                    chapters.append(chapter)

            await session.commit()

            # Refresh chapters to get IDs
            for chapter in chapters:
                await session.refresh(chapter)

            return [BookChapterResponse.model_validate(chapter) for chapter in chapters]

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error extracting chapters for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to extract chapters: {e!s}",
        ) from e


async def batch_update_chapter_statuses(book_id: UUID, updates: list[dict[str, str]]) -> list[BookChapterResponse]:
    """
    Update multiple chapter statuses in one transaction.

    Args:
        book_id: Book ID
        updates: List of dicts with chapter_id and status

    Returns
    -------
        list[BookChapterResponse]: Updated chapters

    Raises
    ------
        HTTPException: If book/chapters not found or update fails
    """
    try:
        async with async_session_maker() as session:
            # Verify book exists
            book_query = select(Book).where(Book.id == book_id)
            book_result = await session.execute(book_query)
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
            chapters_result = await session.execute(chapters_query)
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

            await session.commit()

            # Refresh chapters to get updated timestamps
            for chapter in updated_chapters:
                await session.refresh(chapter)

            return [BookChapterResponse.model_validate(chapter) for chapter in updated_chapters]

    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Error batch updating chapters for book {book_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch update chapters: {e!s}",
        ) from e
