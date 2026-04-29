import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from src.auth import CurrentAuth
from src.books.models import Book
from src.config.schema_casing import build_camel_config
from src.storage.factory import get_storage_provider

from .facade import BooksFacade
from .schemas import (
    BookChapterStatusUpdate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookRagStatus,
    BookResponse,
    BookTocChapterResponse,
    BookUpdate,
    BookWithProgress,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/books", tags=["books"])


def get_books_facade(auth: CurrentAuth) -> BooksFacade:
    """Provide request-scoped books facade."""
    return BooksFacade(auth.session)


@router.get("")
async def list_books(
    auth: CurrentAuth,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    search: Annotated[str | None, Query(description="Search in title, author, or description")] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
) -> BookListResponse:
    """List all books with pagination and optional filtering."""
    return await facade.get_paginated_user_books(
        user_id=auth.user_id,
        page=page,
        limit=limit,
        search=search,
        tags=tags,
    )


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
    auth: CurrentAuth,
    background_tasks: BackgroundTasks,
    facade: Annotated[BooksFacade, Depends(get_books_facade)],
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
        tags_list = json.loads(tags) if tags else []
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid tags format. Expected JSON array.",
        ) from None

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    file_extension = file.filename.lower().split(".")[-1]
    if file_extension not in {"pdf", "epub"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and EPUB files are supported",
        )

    file_content = await file.read()
    return await facade.create_book_from_upload(
        user_id=auth.user_id,
        filename=file.filename,
        file_content=file_content,
        title=title,
        author=author,
        subtitle=subtitle,
        description=description,
        isbn=isbn,
        language=language,
        publication_year=publication_year,
        publisher=publisher,
        tags=tags_list,
        background_tasks=background_tasks,
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

    storage = get_storage_provider()
    url = await storage.get_download_url(book.file_path)

    if url.startswith("http"):
        return RedirectResponse(url)

    media_type = "application/pdf" if book.file_type == "pdf" else "application/epub+zip"

    return FileResponse(
        path=url,
        media_type=media_type,
        headers={"Content-Disposition": "inline"},
    )


@router.get("/{book_id}/presigned-url")
async def get_book_presigned_url(book_id: uuid.UUID, auth: CurrentAuth) -> dict[str, Any]:
    """Get a presigned URL for direct book download from storage."""
    book = await auth.get_or_404(Book, book_id, "book")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    storage = get_storage_provider()
    url = await storage.get_download_url(book.file_path)

    return {
        "url": url,
        "expires_in": 3600,
        "content_type": "application/pdf" if book.file_type == "pdf" else "application/epub+zip",
    }


def _get_media_type(file_type: str) -> str:
    """Get the appropriate media type for a file type."""
    if file_type == "epub":
        return "application/epub+zip"
    if file_type == "pdf":
        return "application/pdf"
    return "application/octet-stream"


def _handle_local_file(url: str, book: Book) -> FileResponse:
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
    url: str,
    range_header: str,
    media_type: str,
    stream_func: Any,
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

                return StreamingResponse(
                    stream_func(),
                    status_code=status.HTTP_206_PARTIAL_CONTENT,
                    media_type=media_type,
                    headers=headers,
                )
        except (httpx.HTTPError, ValueError):
            logger.warning("books.range_request.failed")
    return None


@router.get("/{book_id}/content", response_model=None)
async def stream_book_content(book_id: uuid.UUID, request: Request, auth: CurrentAuth) -> StreamingResponse | FileResponse:
    """Stream book content through backend to avoid CORS issues."""
    book = await auth.get_or_404(Book, book_id, "book")

    if not book.file_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book file not found")

    storage = get_storage_provider()
    url = await storage.get_download_url(book.file_path)

    if not url.startswith("http"):
        return _handle_local_file(url, book)

    media_type = _get_media_type(book.file_type)
    range_header = request.headers.get("range")

    async def stream_content() -> AsyncGenerator[bytes]:
        """Stream content in chunks to avoid loading entire file in memory."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {}
            if range_header:
                headers["Range"] = range_header

            try:
                async with client.stream("GET", url, headers=headers, follow_redirects=True) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        yield chunk
            except httpx.HTTPError:
                logger.exception("books.stream.failed")
                raise

    if range_header:
        range_response = await _handle_range_request(url, range_header, media_type, stream_content)
        if range_response:
            return range_response

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
