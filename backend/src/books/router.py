from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from pydantic import BaseModel

from .metadata import extract_metadata
from .schemas import (
    BookCreate,
    BookListResponse,
    BookProgressResponse,
    BookProgressUpdate,
    BookResponse,
    BookUpdate,
    BookWithProgress,
)
from .service import (
    create_book,
    delete_book,
    get_book,
    get_books,
    update_book,
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
    per_page: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
) -> BookListResponse:
    """List all books with pagination."""
    return await get_books(page=page, per_page=per_page)


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

    file_extension = file.filename.lower().split(".")[-1]
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
        from pathlib import Path

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
    import json

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

    file_extension = file.filename.lower().split(".")[-1]
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

    return await create_book(book_data, file)


@router.put("/{book_id}")
async def update_book_endpoint(book_id: UUID, book_data: BookUpdate) -> BookResponse:
    """Update book details."""
    return await update_book(book_id, book_data)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_book_endpoint(book_id: UUID) -> None:
    """Delete a book."""
    await delete_book(book_id)


@router.put("/{book_id}/progress")
async def update_book_progress_endpoint(
    book_id: UUID,
    progress_data: BookProgressUpdate,
) -> BookProgressResponse:
    """Update reading progress for a book."""
    return await update_book_progress(book_id, progress_data)
