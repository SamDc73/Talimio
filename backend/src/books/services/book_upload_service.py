
import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.books.schemas import BookCreate, BookResponse
from src.books.services.book_metadata_service import BookMetadataService
from src.storage.factory import get_storage_provider
from src.tagging.service import apply_automatic_tagging


if TYPE_CHECKING:
    from src.books.metadata import BookMetadata


from src.ai.rag.background_processor import process_book_rag_background as _process_book_rag_background


ALLOWED_EXTENSIONS = {".pdf", ".epub"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

logger = logging.getLogger(__name__)


class BookUploadService:
    """Service for handling book uploads, validation, and storage."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the book upload service."""
        self.session = session

    async def create_book(
        self, book_data: BookCreate, file: UploadFile, background_tasks: BackgroundTasks, user_id: UUID
    ) -> BookResponse:
        """Create a new book with uploaded file and background embedding processing."""
        try:
            file_content, file_extension, file_hash = await self._validate_and_process_file(file)
            await self._check_duplicate_book(file_hash)

            book_id = uuid4()

            # Extract metadata first
            metadata = self._extract_file_metadata(file_content, file_extension)

            # Upload to storage immediately so user can start reading
            storage_key = await self._upload_file_to_storage(file_content, book_id, file_extension)

            # Create book record with pending RAG status
            book = self._create_book_record(
                book_data,
                storage_key,
                file_content,
                file_hash,
                metadata,
                book_id,
                user_id
            )
            book.rag_status = "pending"  # Will be processed in background
            self.session.add(book)

            # Apply tags
            await apply_automatic_tagging(self.session, book, metadata)

            await self.session.commit()
            await self.session.refresh(book)

            # Schedule background embedding processing
            background_tasks.add_task(_process_book_rag_background, book_id)
            logger.info(f"Scheduled background RAG processing for book {book_id}")

            return self._book_to_response(book)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error creating book")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create book: {e!s}",
            ) from e

    async def _validate_and_process_file(self, file: UploadFile) -> tuple[bytes, str, str]:
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

    async def _check_duplicate_book(self, file_hash: str) -> None:
        existing_book = await self.session.execute(
            select(Book).where(Book.file_hash == file_hash),
        )
        existing_book = existing_book.scalar_one_or_none()

        if existing_book:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"This PDF already exists in the library as '{existing_book.title}' by {existing_book.author}",
            )

    async def _upload_file_to_storage(self, file_content: bytes, book_id: UUID, file_extension: str) -> str:
        storage = get_storage_provider()
        storage_key = f"{book_id}{file_extension}"
        await storage.upload(file_content, storage_key)
        return storage_key

    def _extract_file_metadata(self, file_content: bytes, file_extension: str) -> "BookMetadata":
        metadata_service = BookMetadataService()
        return metadata_service.extract_metadata(file_content, file_extension)

    def _create_book_record(
        self,
        book_data: BookCreate,
        storage_key: str,
        file_content: bytes,
        file_hash: str,
        metadata: "BookMetadata",
        book_id: UUID,
        user_id: UUID
    ) -> Book:
        """Create a Book model instance from the provided data."""
        import json

        # Create the book record
        return Book(
            id=book_id,
            user_id=user_id,
            title=book_data.title or metadata.title or "Unknown Title",
            subtitle=metadata.subtitle,
            author=book_data.author or metadata.author or "Unknown Author",
            description=book_data.description or metadata.description,
            isbn=metadata.isbn,
            language=metadata.language or "en",
            publication_year=metadata.publication_year,
            publisher=metadata.publisher,
            tags=json.dumps(book_data.tags or []),
            file_path=storage_key,
            file_type=metadata.file_type,
            file_size=len(file_content),
            file_hash=file_hash,
            total_pages=metadata.total_pages,
            table_of_contents=json.dumps(metadata.table_of_contents) if metadata.table_of_contents else None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )


    def _book_to_response(self, book: Book) -> BookResponse:
        """Convert Book model to BookResponse with proper tags handling."""
        import json

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
                    toc_list = self._convert_toc_to_schema(toc_data)
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

    def _convert_toc_to_schema(self, toc_data: list) -> list:
        """Convert table of contents data to schema format."""
        from src.books.schemas import TableOfContentsItem

        result = []
        for index, item in enumerate(toc_data):
            if isinstance(item, dict):
                # Generate ID if not present - use existing id or create one based on index and title
                item_id = item.get("id", f"toc-{index}-{item.get('title', 'untitled').lower().replace(' ', '-')[:20]}")

                toc_item = TableOfContentsItem(
                    id=item_id,
                    title=item.get("title", ""),
                    page=item.get("page", 0),
                    level=item.get("level", 0),
                )
                result.append(toc_item)
        return result
