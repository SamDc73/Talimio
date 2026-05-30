import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from src.auth import CurrentAuth
from src.books.models import Book
from src.config.schema_casing import build_camel_config
from src.storage.factory import get_storage_provider

from .facade import BooksFacade
from .schemas import (
    MEDIA_TYPES,
    BookChapterStatusUpdate,
    BookCreate,
    BookProgressResponse,
    BookProgressUpdate,
    BookRagStatus,
    BookResponse,
    BookTocChapterResponse,
    BookUpdate,
    BookWithProgress,
)


router = APIRouter(prefix="/api/v1/books", tags=["books"])


def get_books_facade(auth: CurrentAuth) -> BooksFacade:
    """Provide request-scoped books facade."""
    return BooksFacade(auth.session)


@router.get("/{book_id}")
async def get_book(
    book_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> BookWithProgress:
    """Get book details with progress information."""
    return await facade.get_book(book_id, auth.user_id)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_book(
    book_data: BookCreate,
    auth: CurrentAuth,
    background_tasks: BackgroundTasks,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> BookResponse:
    """Finalize a direct upload to storage and create a book record."""
    filename = book_data.file_path.split("/")[-1]
    return await facade.create_book_from_existing_storage(
        user_id=auth.user_id,
        filename=filename,
        file_path=book_data.file_path,
        storage_provider=book_data.storage_provider,
        title=book_data.title,
        file_size=book_data.file_size,
        author=book_data.author,
        subtitle=book_data.subtitle,
        description=book_data.description,
        isbn=book_data.isbn,
        language=book_data.language,
        publication_year=book_data.publication_year,
        publisher=book_data.publisher,
        tags=book_data.tags,
        background_tasks=background_tasks if book_data.process_in_background else None,
    )


@router.patch("/{book_id}")
async def update_book(
    book_id: uuid.UUID,
    book_data: BookUpdate,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> BookResponse:
    """Update book details."""
    update_dict = book_data.model_dump(exclude_unset=True)
    return await facade.update_book(book_id, auth.user_id, update_dict)


@router.put("/{book_id}/progress")
async def update_book_progress(
    book_id: uuid.UUID,
    progress_data: BookProgressUpdate,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> BookProgressResponse:
    """Update reading progress for a book."""
    return await facade.update_progress_from_request(book_id, auth.user_id, progress_data)


@router.post("/{book_id}/progress")
async def save_book_progress(
    book_id: uuid.UUID,
    progress_data: BookProgressUpdate,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> BookProgressResponse:
    """Update reading progress for a book (POST version for sendBeacon compatibility)."""
    return await facade.update_progress_from_request(book_id, auth.user_id, progress_data)


@router.get("/{book_id}/file", response_model=None)
async def serve_book_file(book_id: uuid.UUID, auth: CurrentAuth) -> FileResponse | RedirectResponse:
    """Serve the actual book file for viewing."""
    book = await auth.get_or_404(Book, book_id, "book")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    storage = get_storage_provider(book.storage_provider)
    url = await storage.get_download_url(book.file_path)

    if url.startswith("http"):
        return RedirectResponse(url)

    media_type = MEDIA_TYPES[book.file_type]

    return FileResponse(
        path=url,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


class BookPresignedUrlResponse(BaseModel):
    """Direct book download URL response."""

    model_config = build_camel_config()

    url: str
    expires_in: int
    content_type: str


@router.get("/{book_id}/presigned-url")
async def get_book_presigned_url(book_id: uuid.UUID, auth: CurrentAuth) -> BookPresignedUrlResponse:
    """Get a presigned URL for direct book download from storage."""
    book = await auth.get_or_404(Book, book_id, "book")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    storage = get_storage_provider(book.storage_provider)
    url = await storage.get_download_url(book.file_path)

    # Local storage returns a filesystem path; the browser must hit our /file route instead.
    if not url.startswith("http"):
        url = f"/api/v1/books/{book_id}/file"

    return BookPresignedUrlResponse(
        url=url,
        expires_in=3600,
        content_type=MEDIA_TYPES[book.file_type],
    )


@router.get("/{book_id}/chapters")
async def get_book_chapters(
    book_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> list[BookTocChapterResponse]:
    """Get all chapters or table-of-contents entries for a book."""
    return await facade.get_book_chapters(book_id, auth.user_id)


@router.put("/{book_id}/chapters/{chapter_id}/status")
async def update_book_chapter_status(
    book_id: uuid.UUID,
    chapter_id: str,
    status_data: BookChapterStatusUpdate,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> BookTocChapterResponse:
    """Update the status of a book chapter."""
    return await facade.update_book_chapter_status(
        book_id=book_id,
        user_id=auth.user_id,
        chapter_id=chapter_id,
        status=status_data.status,
    )


class RAGStatusResponse(BaseModel):
    """Response model for RAG embedding status."""

    model_config = build_camel_config()

    book_id: uuid.UUID
    rag_status: BookRagStatus
    rag_processed_at: str | None = None
    message: str
    chunk_count: int | None = None
    error_details: str | None = None


@router.get("/{book_id}/rag-status")
async def get_book_rag_status(
    book_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
) -> RAGStatusResponse:
    """Get the RAG embedding status for a book."""
    payload = await facade.get_book_rag_status_payload(book_id=book_id, user_id=auth.user_id)
    return RAGStatusResponse.model_validate(payload)
