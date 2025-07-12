import json
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Query, status, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .metadata import extract_metadata
from .schemas import (
    BookChapterBatchUpdateRequest,
    BookChapterResponse,
    BookChapterStatusUpdate,
    BookCreate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
)
from .service import (
    batch_update_chapter_statuses,
    create_book,
    extract_and_create_chapters,
    extract_and_update_toc,
    get_book,
    get_book_chapter,
    get_book_chapters,
    get_books,
    update_book,
    update_book_chapter_status,
    update_book_progress,
)


router = APIRouter(prefix="/api/v1/books", tags=["books"])


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
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> BookListResponse:
    """List all books with pagination."""
    return await get_books(page=page, per_page=limit)


@router.get("/{book_id}")
async def get_book_endpoint(book_id: UUID) -> BookWithProgress:
    """Get book details with progress information."""
    return await get_book(book_id)


@router.post("/extract-metadata")
async def extract_book_metadata(
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
    metadata = extract_metadata(file_content, f".{file_extension}")

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
    background_tasks: BackgroundTasks,
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

    book_data = BookCreate(
        title=title,
        subtitle=subtitle,
        author=author,
        description=description,
        isbn=isbn,
        language=language,
        publication_year=publication_year,
        publisher=publisher,
        tags=tags_list,
        file_type=file_extension,
    )

    return await create_book(book_data, file, background_tasks)


@router.patch("/{book_id}")
async def update_book_endpoint(book_id: UUID, book_data: BookUpdate) -> BookResponse:
    """Update book details."""
    return await update_book(book_id, book_data)


@router.put("/{book_id}/progress")
async def update_book_progress_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
) -> BookProgressResponse:
    """Update reading progress for a book."""
    return await update_book_progress(book_id, progress_data)


@router.post("/{book_id}/progress")
async def update_book_progress_post_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
) -> BookProgressResponse:
    """Update reading progress for a book (POST version for sendBeacon compatibility)."""
    return await update_book_progress(book_id, progress_data)


@router.get("/{book_id}/file")
async def serve_book_file(book_id: UUID) -> FileResponse:
    """Serve the actual book file for viewing."""
    book = await get_book(book_id)

    if not book.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book file not found",
        )

    # Ensure the file exists
    file_path = Path(book.file_path)
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Book file not found on disk",
        )

    # Determine media type based on file extension
    media_type = "application/pdf" if book.file_type == "pdf" else "application/epub+zip"

    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


@router.post("/{book_id}/extract-toc")
async def extract_table_of_contents(book_id: UUID) -> BookResponse:
    """Extract and update table of contents for an existing book."""
    return await extract_and_update_toc(book_id)


# Phase 2.2: Book Chapter Endpoints
@router.get("/{book_id}/chapters")
async def get_book_chapters_endpoint(book_id: UUID) -> list[BookChapterResponse]:
    """Get all chapters for a book."""
    return await get_book_chapters(book_id)


@router.get("/{book_id}/chapters/{chapter_id}")
async def get_book_chapter_endpoint(book_id: UUID, chapter_id: UUID) -> BookChapterResponse:
    """Get a specific chapter for a book."""
    return await get_book_chapter(book_id, chapter_id)


@router.put("/{book_id}/chapters/{chapter_id}/status")
async def update_book_chapter_status_endpoint(
    book_id: UUID,
    chapter_id: UUID,
    status_data: BookChapterStatusUpdate,
) -> BookChapterResponse:
    """Update the status of a book chapter."""
    return await update_book_chapter_status(book_id, chapter_id, status_data.status)


@router.put("/{book_id}/chapters/batch-status")
async def batch_update_chapter_statuses_endpoint(
    book_id: UUID,
    request: BookChapterBatchUpdateRequest,
) -> list[BookChapterResponse]:
    """Update multiple chapter statuses in one atomic transaction."""
    updates = [{"chapter_id": str(update.chapter_id), "status": update.status} for update in request.updates]
    return await batch_update_chapter_statuses(book_id, updates)


@router.post("/{book_id}/extract-chapters")
async def extract_chapters_endpoint(book_id: UUID) -> list[BookChapterResponse]:
    """Extract chapters from book's table of contents."""
    return await extract_and_create_chapters(book_id)
