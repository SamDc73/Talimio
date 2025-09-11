from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator, Callable
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from src.auth import CurrentAuth
from src.books.models import Book
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

router = APIRouter(prefix="/api/v1/books", tags=["books"], dependencies=[Depends(books_rate_limit)])


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


def _convert_to_progress_response(progress: dict, book_id: UUID) -> BookProgressResponse:
    """Convert progress dict to response format."""
    return BookProgressResponse(
        id=progress.get("id"),  # None if not yet saved to database
        book_id=book_id,
        current_page=progress.get("page", progress.get("current_page", 1)),
        progress_percentage=progress.get("completion_percentage", 0),
        total_pages_read=progress.get("total_pages_read", progress.get("page", 1)),
        reading_time_minutes=progress.get("reading_time_minutes", 0),
        status=progress.get("status", "not_started"),
        notes=progress.get("notes"),
        bookmarks=progress.get("bookmarks", []),
        toc_progress=progress.get("toc_progress", {}),
        last_read_at=progress.get("last_accessed_at", progress.get("last_read_at")),
        created_at=progress.get("created_at"),  # None if not yet saved
        updated_at=progress.get("updated_at"),  # None if not yet saved
    )


@router.get("")
async def list_books(
    auth: CurrentAuth,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search in title, author, or description")] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
) -> BookListResponse:
    """List all books with pagination and optional filtering."""
    try:
        # Get books through facade
        result = await books_facade.get_user_books(auth.user_id, include_progress=True)

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
async def get_book_endpoint(book_id: UUID, auth: CurrentAuth) -> BookWithProgress:
    """Get book details with progress information."""
    try:
        result = await books_facade.get_book_with_progress(book_id, auth.user_id)

        if not result.get("success"):
            if "not found" in result.get("error", "").lower():
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.get("error", "Failed to get book")
            )

        book = result.get("book", {})
        progress = result.get("progress", {})

        # Convert to BookWithProgress format
        # Create a proper BookResponse first
        book_response = BookResponse(
            id=book.get("id"),
            title=book.get("title"),
            author=book.get("author"),
            subtitle=book.get("subtitle"),
            description=book.get("description"),
            isbn=book.get("isbn"),
            language=book.get("language"),
            publication_year=book.get("publication_year"),
            publisher=book.get("publisher"),
            tags=book.get("tags", []),
            file_type=book.get("file_type"),
            file_path=book.get("file_path"),
            file_size=book.get("file_size"),
            total_pages=book.get("total_pages"),
            table_of_contents=book.get("table_of_contents"),
            rag_status=book.get("rag_status"),
            rag_processed_at=book.get("rag_processed_at"),
            created_at=book.get("created_at"),
            updated_at=book.get("updated_at"),
        )

        return BookWithProgress(
            id=book_response.id,
            title=book_response.title,
            author=book_response.author,
            subtitle=book_response.subtitle,
            description=book_response.description,
            isbn=book_response.isbn,
            language=book_response.language,
            publication_year=book_response.publication_year,
            publisher=book_response.publisher,
            tags=book_response.tags,
            file_type=book_response.file_type,
            file_path=book_response.file_path,
            file_size=book_response.file_size,
            total_pages=book_response.total_pages,
            table_of_contents=book_response.table_of_contents,
            rag_status=book_response.rag_status,
            rag_processed_at=book_response.rag_processed_at,
            created_at=book_response.created_at,
            updated_at=book_response.updated_at,
            progress=BookProgressResponse(
                id=progress.get("id"),  # None if not yet saved to database
                book_id=book_id,
                current_page=progress.get("current_page", 1),
                progress_percentage=progress.get("completion_percentage", 0),
                total_pages_read=progress.get("total_pages_read", progress.get("page", 1)),
                reading_time_minutes=progress.get("reading_time_minutes", 0),
                status=progress.get("status", "not_started"),
                notes=progress.get("notes"),
                bookmarks=progress.get("bookmarks", []),
                toc_progress=progress.get("toc_progress", {}),
                last_read_at=progress.get("last_read_at"),
                created_at=progress.get("created_at"),  # None if not yet saved
                updated_at=progress.get("updated_at"),  # None if not yet saved
            )
            if progress
            else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_book_endpoint(
    auth: CurrentAuth,
    file: Annotated[UploadFile, File(description="Book file (PDF or EPUB)")],
    title: Annotated[str, Form(description="Book title")],
    author: Annotated[str | None, Form(description="Book author")] = None,
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
        storage_key = f"books/{auth.user_id!s}/{file.filename}"
        logger.info(f"Uploading file to storage: {storage_key}")

        # Upload the file (returns None, we use the key as the path)
        await storage.upload(file_content, storage_key)

        # The file path is the storage key we used
        file_path = storage_key
        logger.info(f"File uploaded with key: {file_path}")

        # Extract metadata if needed
        metadata_service = BookMetadataService()
        metadata = metadata_service.extract_metadata(file_content, f".{file_extension}")
        logger.info(
            f"Extracted metadata - title: {metadata.title}, author: {metadata.author}, pages: {metadata.total_pages}"
        )

        # Calculate file hash
        import hashlib

        file_hash = hashlib.sha256(file_content).hexdigest()

        # Smart metadata priority: use extracted metadata when form data looks like filename hints
        filename_without_ext = file.filename.rsplit(".", 1)[0] if file.filename else ""

        # Use extracted title if it exists and form title looks like filename
        final_title = title
        if metadata.title and (not title or title == filename_without_ext):
            final_title = metadata.title

        # Use extracted author if it exists and no author provided or author is empty
        final_author = author
        if metadata.author and (not author or not author.strip()):
            final_author = metadata.author

        # Build book data combining form data with extracted metadata
        book_metadata = {
            "title": final_title,
            "subtitle": subtitle or metadata.subtitle,
            "author": final_author,
            "description": description or metadata.description,
            "isbn": isbn or metadata.isbn,
            "language": language or metadata.language,
            "publication_year": publication_year or metadata.publication_year,
            "publisher": publisher or metadata.publisher,
            "tags": tags_list,
            "file_type": file_extension,
            "file_size": len(file_content),
            "total_pages": metadata.total_pages or 0,
            "file_hash": file_hash,
            "table_of_contents": json.dumps(metadata.table_of_contents) if metadata.table_of_contents else None,
        }

        # Upload book through facade
        result = await books_facade.upload_book(
            file_path=file_path, title=final_title, user_id=auth.user_id, metadata=book_metadata
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
async def update_book_endpoint(book_id: UUID, book_data: BookUpdate, auth: CurrentAuth) -> BookResponse:
    """Update book details."""
    try:
        # Convert Pydantic model to dict
        update_dict = book_data.model_dump(exclude_unset=True)

        result = await books_facade.update_book(book_id, auth.user_id, update_dict)

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
async def delete_book_endpoint(book_id: UUID, auth: CurrentAuth, db: DbSession) -> None:
    """Delete a book."""
    try:
        await books_facade.delete_book(db, book_id, auth.user_id)
        await db.commit()
    except ValueError as e:
        # Book not found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error deleting book {book_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.put("/{book_id}/progress")
async def update_book_progress_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
    auth: CurrentAuth,
) -> BookProgressResponse:
    """Update reading progress for a book.

    Note: Progress percentage is now calculated on-demand from ToC progress
    in the content endpoint, similar to how course progress works.
    This ensures homepage always shows accurate progress.
    """
    try:
        # Convert progress data to dict for facade
        progress_dict = _build_progress_dict(progress_data)

        result = await books_facade.update_book_progress(book_id, auth.user_id, progress_dict)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update progress"),
            )

        progress = result.get("progress", {})
        return _convert_to_progress_response(progress, book_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating book progress: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/{book_id}/progress")
async def update_book_progress_post_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
    auth: CurrentAuth,
) -> BookProgressResponse:
    """Update reading progress for a book (POST version for sendBeacon compatibility)."""
    # Delegate to the PUT endpoint handler
    return await update_book_progress_endpoint(book_id, progress_data, auth)


@router.get("/{book_id}/file", response_model=None)
async def serve_book_file(book_id: UUID, auth: CurrentAuth, db: DbSession) -> FileResponse | RedirectResponse:
    """Serve the actual book file for viewing."""
    # Simple direct database query
    from sqlalchemy import select

    from src.books.models import Book

    query = select(Book).where(Book.id == book_id, Book.user_id == auth.user_id)
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


@router.get("/{book_id}/presigned-url")
async def get_book_presigned_url(book_id: UUID, auth: CurrentAuth, db: DbSession) -> dict:
    """Get a presigned URL for direct book download from R2/storage.

    This is useful when you want the browser to directly download from R2
    without proxying through the backend.
    """
    from sqlalchemy import select

    from src.books.models import Book

    query = select(Book).where(Book.id == book_id, Book.user_id == auth.user_id)
    result = await db.execute(query)
    book = result.scalar_one_or_none()

    if not book:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    # Get storage provider and presigned URL
    storage = get_storage_provider()
    url = await storage.get_download_url(book.file_path, expires_in=3600)  # 1 hour expiry

    return {
        "url": url,
        "expires_in": 3600,
        "content_type": "application/pdf" if book.file_type == "pdf" else "application/epub+zip",
        "filename": f"{book.title}.{book.file_type}",
    }


def _get_media_type(file_type: str) -> str:
    """Get the appropriate media type for a file type."""
    if file_type == "epub":
        return "application/epub+zip"
    if file_type == "pdf":
        return "application/pdf"
    return "application/octet-stream"


async def _handle_local_file(url: str, book: Book) -> FileResponse:
    """Handle serving local files."""
    media_type = _get_media_type(book.file_type)

    return FileResponse(
        path=url,
        media_type=media_type,
        filename=f"{book.title}.{book.file_type}",
        headers={
            "Cache-Control": "private, max-age=3600",
            "Accept-Ranges": "bytes",
            "Content-Type": media_type,
        },
    )


async def _handle_range_request(
    url: str, range_header: str, media_type: str, stream_func: Callable[[], AsyncGenerator[bytes, None]]
) -> StreamingResponse | None:
    """Handle range requests for partial content."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            head_response = await client.head(url, follow_redirects=True)
            content_length = head_response.headers.get("content-length")

            import re

            range_match = re.match(r"bytes=(\d+)-(\d*)", range_header)
            if range_match and content_length:
                start = int(range_match.group(1))
                end = int(range_match.group(2)) if range_match.group(2) else int(content_length) - 1

                headers = {
                    "Content-Range": f"bytes {start}-{end}/{content_length}",
                    "Accept-Ranges": "bytes",
                    "Content-Length": str(end - start + 1),
                    "Cache-Control": "private, max-age=3600",
                }

                return StreamingResponse(stream_func(), status_code=206, media_type=media_type, headers=headers)
        except Exception as e:
            logger.warning(f"Range request failed: {e}")
    return None


@router.get("/{book_id}/content", response_model=None)
async def stream_book_content(
    book_id: UUID, request: Request, auth: CurrentAuth, db: DbSession
) -> StreamingResponse | FileResponse:
    """Stream book PDF content through backend to avoid CORS issues.

    This endpoint acts as a proxy, fetching the book from storage and
    streaming it back to the client. This completely bypasses CORS issues
    with signed URLs. Supports range requests for efficient PDF loading.
    """
    # Simple direct database query
    from sqlalchemy import select

    from src.books.models import Book

    query = select(Book).where(Book.id == book_id, Book.user_id == auth.user_id)
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
        return await _handle_local_file(url, book)

    # For remote storage, properly stream with range support
    media_type = _get_media_type(book.file_type)

    # Check if this is a range request
    range_header = request.headers.get("range")

    async def stream_content() -> AsyncGenerator[bytes, None]:
        """Stream content in chunks to avoid loading entire file in memory."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Make request with range header if provided
            headers = {}
            if range_header:
                headers["Range"] = range_header

            try:
                async with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
                    response.raise_for_status()

                    # Stream in chunks
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        yield chunk

            except httpx.HTTPError as e:
                logger.exception(f"Failed to stream book content: {e}")
                # Yield empty to avoid broken pipe
                yield b""

    # For range requests, we need to get content-length first
    if range_header:
        range_response = await _handle_range_request(url, range_header, media_type, stream_content)
        if range_response:
            return range_response

    # Normal streaming response (no range)
    return StreamingResponse(
        stream_content(),
        media_type=media_type,
        headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, max-age=3600",
            "Content-Disposition": f'inline; filename="{book.title}.{book.file_type}"',
        },
    )


@router.get("/{book_id}/chapters")
async def get_book_chapters_endpoint(book_id: UUID, auth: CurrentAuth) -> list[dict]:
    """Get all chapters/table of contents for a book.

    Returns the table of contents structure, not database chapter records.
    """
    try:
        result = await books_facade.get_book_chapters(book_id, auth.user_id)

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
    auth: CurrentAuth,
) -> BookChapterResponse:
    """Update the status of a book chapter."""
    try:
        # Use mark_chapter_complete on the facade
        completed = status_data.status == "completed"
        result = await books_facade.mark_chapter_complete(book_id, auth.user_id, str(chapter_id), completed)

        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get("error", "Failed to update chapter status"),
            )

        # Return a chapter response with required fields
        return BookChapterResponse(
            id=chapter_id,
            book_id=book_id,
            chapter_number=1,  # This is just a placeholder since we're using TOC chapter IDs
            title="Chapter",  # Placeholder title
            start_page=None,
            end_page=None,
            status=status_data.status,
            created_at=None,  # Not from database, just a status update response
            updated_at=None,  # Not from database, just a status update response
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
async def get_book_rag_status(book_id: UUID, auth: CurrentAuth) -> RAGStatusResponse:
    """Get the RAG embedding status for a book."""
    from sqlalchemy import select

    from src.books.models import Book
    from src.database.session import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(select(Book).where(Book.id == book_id, Book.user_id == auth.user_id))
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
