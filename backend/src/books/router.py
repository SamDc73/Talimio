import json
import logging
from io import BytesIO
from pathlib import Path
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from src.auth import UserId
from src.database.session import DbSession
from src.middleware.security import books_rate_limit
from src.storage.factory import get_storage_provider

# Import the facade
from .facade import BooksFacade
from .schemas import (
    BookChapterResponse,
    BookChapterStatusUpdate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
)
from .services.book_metadata_service import BookMetadataService


logger = logging.getLogger(__name__)

# Create facade instance
books_facade = BooksFacade()

router = APIRouter(
    prefix="/api/v1/books",
    tags=["books"],
    dependencies=[Depends(books_rate_limit)]
)


def _build_progress_dict(progress_data: BookProgressUpdate) -> dict:
    """Build progress dictionary from update request."""
    progress_dict = {}

    # Map current_page to page for internal use
    if progress_data.current_page is not None:
        progress_dict["page"] = progress_data.current_page

    if progress_data.progress_percentage is not None:
        progress_dict["completion_percentage"] = progress_data.progress_percentage

    if progress_data.toc_progress is not None:
        progress_dict["toc_progress"] = progress_data.toc_progress

    if progress_data.bookmarks is not None:
        progress_dict["bookmarks"] = progress_data.bookmarks

    if progress_data.status is not None:
        progress_dict["status"] = progress_data.status

    if progress_data.notes is not None:
        progress_dict["notes"] = progress_data.notes

    if progress_data.reading_time_minutes is not None:
        progress_dict["reading_time_minutes"] = progress_data.reading_time_minutes

    return progress_dict


def _convert_to_progress_response(progress: dict, book_id: UUID, user_id: UUID) -> BookProgressResponse:
    """Convert progress dict to response format."""
    from datetime import UTC, datetime

    return BookProgressResponse(
        id=progress.get("id", UUID("00000000-0000-0000-0000-000000000000")),
        book_id=book_id,
        user_id=user_id,
        current_page=progress.get("page", progress.get("current_page", 1)),
        progress_percentage=progress.get("completion_percentage", 0),
        zoom_level=progress.get("zoom_level", 100),
        completed_chapters=progress.get("completed_chapters", {}),
        total_pages_read=progress.get("page", 1),  # Add this field
        last_read_at=progress.get("last_accessed_at", progress.get("last_read_at")),
        created_at=progress.get("created_at", datetime.now(UTC)),
        updated_at=progress.get("updated_at", datetime.now(UTC)),
    )


class BookMetadataResponse(BaseModel):
    """Response model for book metadata extraction."""

    title: str | None = None
    author: str | None = None
    description: str | None = None
    language: str | None = None
    publisher: str | None = None
    isbn: str | None = None
    publication_year: int | None = None
    page_count: int | None = None


@router.get("")
async def list_books(
    user_id: UserId,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search in title, author, or description")] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
) -> BookListResponse:
    """List all books with pagination and optional filtering."""
    try:
        # Get books through facade
        result = await books_facade.get_user_books(user_id, include_progress=True)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to get books")
            )

        books = result.get("books", [])

        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            books = [
                book
                for book in books
                if search_lower in (book.title or "").lower()
                or search_lower in (book.author or "").lower()
                or search_lower in (book.description or "").lower()
            ]

        # Apply tag filter if provided
        if tags:
            books = [book for book in books if any(tag in (book.tags or []) for tag in tags)]

        # Pagination
        total = len(books)
        start = (page - 1) * limit
        end = start + limit
        paginated_books = books[start:end]

        # Convert to response format
        return BookListResponse(
            items=[BookResponse.model_validate(book) for book in paginated_books],
            total=total,
            page=page,
            pages=(total + limit - 1) // limit,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error listing books: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{book_id}")
async def get_book_endpoint(book_id: UUID, user_id: UserId) -> BookWithProgress:
    """Get book details with progress information."""
    try:
        result = await books_facade.get_book_with_progress(book_id, user_id)

        if not result.get("success"):
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to get book")
            )

        book = result.get("book", {})
        progress = result.get("progress", {})

        # Convert to BookWithProgress format
        from datetime import UTC, datetime

        return BookWithProgress(
            **book,
            progress=BookProgressResponse(
                id=progress.get("id", UUID("00000000-0000-0000-0000-000000000000")),
                book_id=book_id,
                user_id=user_id,
                current_page=progress.get("current_page", 1),
                progress_percentage=progress.get("completion_percentage", 0),
                zoom_level=progress.get("zoom_level", 100),
                completed_chapters=progress.get("completed_chapters", {}),
                total_pages_read=progress.get("page", 1),  # Add this field
                last_read_at=progress.get("last_read_at"),
                created_at=progress.get("created_at", datetime.now(UTC)),
                updated_at=progress.get("updated_at", datetime.now(UTC)),
            )
            if progress
            else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/extract-metadata")
async def extract_book_metadata(
    user_id: UserId,
    file: Annotated[UploadFile, File(description="Book file (PDF or EPUB) to extract metadata from")],
) -> BookMetadataResponse:
    """Extract metadata from a book file without storing it."""
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    file_extension = (file.filename or "").lower().split(".")[-1]
    if file_extension not in ["pdf", "epub"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and EPUB files are supported",
        )

    # Read file content
    file_content = await file.read()

    # Extract metadata
    metadata_service = BookMetadataService()
    metadata = metadata_service.extract_metadata(file_content, f".{file_extension}")

    # If no title was extracted, use filename without extension
    if not metadata.title:
        metadata.title = Path(file.filename).stem

    return BookMetadataResponse(
        title=metadata.title,
        author=metadata.author,
        description=metadata.description,
        language=metadata.language,
        publisher=metadata.publisher,
        isbn=metadata.isbn,
        publication_year=metadata.publication_year,
        page_count=metadata.page_count,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_book_endpoint(
    user_id: UserId,
    file: Annotated[UploadFile, File(description="Book file (PDF or EPUB)")],
    title: Annotated[str, Form(description="Book title")],
    author: Annotated[str, Form(description="Book author")],
    subtitle: Annotated[str | None, Form(description="Book subtitle")] = None,
    description: Annotated[str | None, Form(description="Book description")] = None,
    isbn: Annotated[str | None, Form(description="ISBN")] = None,
    language: Annotated[str | None, Form(description="Language code")] = None,
    publication_year: Annotated[int | None, Form(description="Publication year")] = None,
    publisher: Annotated[str | None, Form(description="Publisher")] = None,
    tags: Annotated[str, Form(description="Tags as JSON array string")] = "[]",
) -> BookResponse:
    """Add a new book (PDF, EPUB)."""
    try:
        # Parse tags from JSON string
        try:
            tags_list = json.loads(tags) if tags else []
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tags format. Expected JSON array.",
            ) from None

        # Determine file type from filename
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No filename provided",
            )

        file_extension = (file.filename or "").lower().split(".")[-1]
        if file_extension not in ["pdf", "epub"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only PDF and EPUB files are supported",
            )

        # Upload file to storage
        storage = get_storage_provider()
        file_content = await file.read()

        # Generate the storage key
        storage_key = f"books/{user_id}/{file.filename}"
        logger.info(f"Uploading file to storage: {storage_key}")

        # Upload the file (returns None, we use the key as the path)
        await storage.upload(file_content, storage_key)

        # The file path is the storage key we used
        file_path = storage_key
        logger.info(f"File uploaded with key: {file_path}")

        # Extract metadata if needed
        metadata_service = BookMetadataService()
        metadata = metadata_service.extract_metadata(file_content, f".{file_extension}")

        # Calculate file hash
        import hashlib

        file_hash = hashlib.sha256(file_content).hexdigest()

        # Build book data combining form data with extracted metadata
        book_metadata = {
            "title": title,
            "subtitle": subtitle,
            "author": author,
            "description": description,
            "isbn": isbn,
            "language": language or metadata.language,
            "publication_year": publication_year or metadata.publication_year,
            "publisher": publisher or metadata.publisher,
            "tags": tags_list,
            "file_type": file_extension,
            "file_size": len(file_content),
            "total_pages": metadata.page_count or 0,
            "file_hash": file_hash,
        }

        # Upload book through facade
        result = await books_facade.upload_book(
            file_path=file_path, title=title, user_id=user_id, metadata=book_metadata
        )

        if not result.get("success"):
            # Clean up uploaded file on failure
            try:
                await storage.delete(storage_key)
            except Exception:
                logger.debug("Failed to clean up uploaded file")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to create book")
            )

        book = result.get("book", {})
        return BookResponse.model_validate(book)

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error creating book: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.patch("/{book_id}")
async def update_book_endpoint(book_id: UUID, book_data: BookUpdate, user_id: UserId) -> BookResponse:
    """Update book details."""
    try:
        # Convert Pydantic model to dict
        update_dict = book_data.model_dump(exclude_unset=True)

        result = await books_facade.update_book(book_id, user_id, update_dict)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to update book")
            )

        book = result.get("book", {})
        return BookResponse.model_validate(book)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error updating book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.delete("/{book_id}")
async def delete_book_endpoint(book_id: UUID, user_id: UserId) -> None:
    """Delete a book."""
    try:
        success = await books_facade.delete_book(book_id, user_id)
        if not success:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.put("/{book_id}/progress")
async def update_book_progress_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
    user_id: UserId,
) -> BookProgressResponse:
    """Update reading progress for a book.

    Note: Progress percentage is now calculated on-demand from ToC progress
    in the content endpoint, similar to how course progress works.
    This ensures homepage always shows accurate progress.
    """
    try:
        # Convert progress data to dict for facade
        progress_dict = _build_progress_dict(progress_data)

        result = await books_facade.update_book_progress(book_id, user_id, progress_dict)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update progress"),
            )

        progress = result.get("progress", {})
        return _convert_to_progress_response(progress, book_id, user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating book progress: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/{book_id}/progress")
async def update_book_progress_post_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
    user_id: UserId,
) -> BookProgressResponse:
    """Update reading progress for a book (POST version for sendBeacon compatibility)."""
    # Delegate to the PUT endpoint handler
    return await update_book_progress_endpoint(book_id, progress_data, user_id)


@router.get("/{book_id}/file", response_model=None)
async def serve_book_file(book_id: UUID, user_id: UserId, db: DbSession) -> FileResponse | RedirectResponse:
    """Serve the actual book file for viewing."""
    # Simple direct database query
    from sqlalchemy import select

    from src.books.models import Book

    query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    # Get storage provider and download URL
    storage = get_storage_provider()
    url = await storage.get_download_url(book.file_path)

    if url.startswith("http"):
        # For R2 storage, redirect to the presigned URL
        return RedirectResponse(url)

    # For local storage, url is an absolute path
    media_type = "application/pdf" if book.file_type == "pdf" else "application/epub+zip"

    return FileResponse(
        path=url,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/{book_id}/content", response_model=None)
async def stream_book_content(book_id: UUID, user_id: UserId, db: DbSession) -> StreamingResponse:
    """Stream book PDF content through backend to avoid CORS issues.

    This endpoint acts as a proxy, fetching the book from storage and
    streaming it back to the client. This completely bypasses CORS issues
    with signed URLs.
    """
    # Simple direct database query
    from sqlalchemy import select

    from src.books.models import Book

    query = select(Book).where(Book.id == book_id, Book.user_id == user_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    # Get storage provider and download URL
    storage = get_storage_provider()
    url = await storage.get_download_url(book.file_path)

    # If it's a local file, serve it directly
    if not url.startswith("http"):
        from fastapi.responses import FileResponse

        media_type = "application/pdf" if book.file_type == "pdf" else "application/epub+zip"
        return FileResponse(
            path=url,
            media_type=media_type,
            filename=f"{book.title}.{book.file_type}",
            headers={
                "Cache-Control": "private, max-age=3600",
            }
        )

    # For remote storage, fetch and stream
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()

            media_type = "application/pdf" if book.file_type == "pdf" else "application/epub+zip"

            return StreamingResponse(
                BytesIO(response.content),
                media_type=media_type,
                headers={
                    "Content-Disposition": f'inline; filename="{book.title}.{book.file_type}"',
                    "Cache-Control": "private, max-age=3600",  # Cache for 1 hour
                }
            )
        except httpx.HTTPError as e:
            logger.exception("Failed to fetch book content")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve book content"
            ) from e


@router.post("/{book_id}/extract-toc")
async def extract_table_of_contents(book_id: UUID, user_id: UserId) -> BookResponse:
    """Extract and update table of contents for an existing book."""
    try:
        # TODO: Implement TOC extraction in facade
        # For now, just return the book as-is
        result = await books_facade.get_book_with_progress(book_id, user_id)

        if not result.get("success"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        book = result.get("book", {})
        return BookResponse.model_validate(book)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error extracting ToC for book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{book_id}/chapters")
async def get_book_chapters_endpoint(book_id: UUID, user_id: UserId) -> list[dict]:
    """Get all chapters/table of contents for a book.

    Returns the table of contents structure, not database chapter records.
    """
    try:
        result = await books_facade.get_book_chapters(book_id, user_id)

        if not result.get("success"):
            # Check if it's a "not found" error
            error_msg = result.get("error", "Failed to get chapters")
            if "not found" in error_msg.lower():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Book {book_id} not found")
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg)

        return result.get("chapters", [])
        # Return raw TOC data - don't try to validate as BookChapterResponse
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting book chapters: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.put("/{book_id}/chapters/{chapter_id}/status")
async def update_book_chapter_status_endpoint(
    book_id: UUID,
    chapter_id: UUID,
    status_data: BookChapterStatusUpdate,
    user_id: UserId,
) -> BookChapterResponse:
    """Update the status of a book chapter."""
    try:
        # Use mark_chapter_complete on the facade
        completed = status_data.status == "completed"
        result = await books_facade.mark_chapter_complete(book_id, user_id, str(chapter_id), completed)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update chapter status"),
            )

        # Return a chapter response - for now just return success
        return BookChapterResponse(
            id=chapter_id,
            book_id=book_id,
            chapter_id=str(chapter_id),
            status=status_data.status,
            completed_at=None,
            created_at=None,
            updated_at=None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating chapter status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


class RAGStatusResponse(BaseModel):
    """Response model for RAG embedding status."""

    book_id: UUID
    rag_status: str  # pending, processing, completed, failed
    rag_processed_at: str | None = None
    message: str
    chunk_count: int | None = None  # Number of chunks processed (if available)
    error_details: str | None = None  # Error details if failed


@router.get("/{book_id}/rag-status")
async def get_book_rag_status(book_id: UUID, user_id: UserId) -> RAGStatusResponse:
    """Get the RAG embedding status for a book."""
    from sqlalchemy import select

    from src.books.models import Book
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(
            select(Book).where(Book.id == book_id, Book.user_id == user_id)
        )
        book = result.scalar_one_or_none()

        if not book:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

        # Generate status message
        status_messages = {
            "pending": "Book is ready to read! AI chat will be available once processing completes.",
            "processing": "Book is being processed for AI chat. You can start reading now!",
            "completed": "Book is ready! AI chat is now available.",
            "failed": "Processing failed. AI chat is not available, but you can still read the book.",
        }

        # Get chunk count if available
        chunk_count = None
        if book.rag_status in ["completed", "processing"]:
            try:
                from sqlalchemy import text

                count_result = await session.execute(
                    text("SELECT COUNT(*) FROM rag_document_chunks WHERE doc_id = :doc_id"), {"doc_id": str(book_id)}
                )
                chunk_count = count_result.scalar()
            except Exception:
                logger.debug("Could not count RAG chunks")

        # Get error details if failed
        error_details = None
        if book.rag_status == "failed" and hasattr(book, "rag_error"):
            error_details = getattr(book, "rag_error", None)

        return RAGStatusResponse(
            book_id=book_id,
            rag_status=book.rag_status,
            rag_processed_at=book.rag_processed_at.isoformat() if book.rag_processed_at else None,
            message=status_messages.get(book.rag_status, "Unknown status"),
            chunk_count=chunk_count,
            error_details=error_details,
        )
