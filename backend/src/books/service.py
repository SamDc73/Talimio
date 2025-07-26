import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.books.schemas import (
    BookCreate,
    BookListResponse,
    BookResponse,
    BookUpdate,
    TableOfContentsItem,
)
from src.core.mode_aware_service import ModeAwareService
from src.database.pagination import Paginator
from src.database.session import async_session_maker
from src.storage.factory import get_storage_provider
from src.tagging.service import TaggingService


logger = logging.getLogger(__name__)


def parse_book_id(book_id: str) -> UUID:
    """Convert string UUID to UUID object with validation."""
    try:
        return UUID(book_id)
    except ValueError as e:
        msg = f"Invalid UUID format: {book_id}"
        raise ValueError(msg) from e


class BookService(ModeAwareService):
    """Service for managing books."""

    def __init__(self) -> None:
        """Initialize the book service."""
        super().__init__()

    def _book_to_dict(self, book: Book) -> dict[str, Any]:
        """Convert Book SQLAlchemy object to dict to avoid lazy loading issues."""
        # Parse tags if stored as JSON
        tags_list = []
        if book.tags:
            try:
                tags_list = json.loads(book.tags)
            except (json.JSONDecodeError, TypeError):
                tags_list = []

        # Parse table of contents if stored as JSON
        toc_list = None
        if book.table_of_contents:
            try:
                toc_data = json.loads(book.table_of_contents)
                if isinstance(toc_data, list):
                    toc_list = self._convert_toc_to_schema(toc_data)
            except (json.JSONDecodeError, TypeError):
                toc_list = None

        return {
            "id": book.id,
            "uuid": book.id,  # Map id to uuid for schema compatibility
            "title": book.title,
            "subtitle": book.subtitle,
            "author": book.author,
            "description": book.description,
            "isbn": book.isbn,
            "language": book.language,
            "publication_year": book.publication_year,
            "publisher": book.publisher,
            "tags": tags_list,
            "file_path": book.file_path,
            "file_type": book.file_type,
            "file_size": book.file_size,
            "total_pages": book.total_pages,
            "table_of_contents": toc_list,
            "rag_status": book.rag_status,
            "rag_processed_at": book.rag_processed_at,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
        }

    def _convert_toc_to_schema(self, toc_data: list[dict]) -> list[TableOfContentsItem]:
        """Convert table of contents data to schema objects."""
        result = []
        for item in toc_data:
            children = []
            if item.get("children"):
                children = self._convert_toc_to_schema(item["children"])

            toc_item = TableOfContentsItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                page=item.get("page", 1),
                children=children,
                level=item.get("level", 0)
            )
            result.append(toc_item)
        return result

    async def process_book_upload(
        self,
        file_path: str,
        title: str,
        user_id: UUID,
        additional_metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process book file upload and create book record."""
        try:
            # Extract metadata from the file if needed
            metadata = additional_metadata or {}

            logger.info(f"Processing book upload: file_path={file_path}, title={title}")
            logger.info(f"Metadata: {metadata}")

            # Create book data using only fields from BookCreate schema
            book_data = BookCreate(
                title=title,
                file_type=metadata.get("file_type", "pdf"),
                author=metadata.get("author", "Unknown"),
                subtitle=metadata.get("subtitle"),
                description=metadata.get("description"),
                isbn=metadata.get("isbn"),
                language=metadata.get("language", "en"),
                publication_year=metadata.get("publication_year"),
                publisher=metadata.get("publisher"),
                tags=metadata.get("tags", [])
            )

            # Add extra fields for internal use
            extra_data = {
                "file_path": file_path,
                "file_size": metadata.get("file_size", 0),
                "total_pages": metadata.get("total_pages", 0),
                "file_hash": metadata.get("file_hash"),
            }

            logger.info(f"Extra data: {extra_data}")

            # Create book in database
            async with async_session_maker() as db:
                book_response = await self.create_book(db, book_data, user_id, extra_data)

                return {
                    "book": book_response.model_dump(),
                    "success": True
                }

        except Exception as e:
            logger.exception(f"Error processing book upload: {e}")
            return {
                "error": str(e),
                "success": False
            }

    async def create_book(
        self, db: AsyncSession, book_data: BookCreate, user_id: UUID, extra_data: dict[str, Any] | None = None
    ) -> BookResponse:
        """Create a new book record."""
        # Log the access
        self.log_access("create", user_id, "book")

        # Get the user ID for creation
        query_builder = self.get_query_builder(Book)
        user_id_for_creation = query_builder.apply_user_filter_for_creation(user_id)

        # Merge extra data if provided
        extra_data = extra_data or {}

        # Create book record
        book = Book(
            user_id=user_id_for_creation,
            title=book_data.title,
            subtitle=book_data.subtitle,
            author=book_data.author,
            description=book_data.description,
            isbn=book_data.isbn,
            language=book_data.language,
            publication_year=book_data.publication_year,
            publisher=book_data.publisher,
            tags=json.dumps(book_data.tags) if book_data.tags else None,
            file_path=extra_data.get("file_path", ""),
            file_type=book_data.file_type,
            file_size=extra_data.get("file_size", 0),
            total_pages=extra_data.get("total_pages", 0),
            file_hash=extra_data.get("file_hash"),  # Add file_hash from extra_data
        )

        db.add(book)
        try:
            await db.commit()
            await db.refresh(book)
        except IntegrityError as e:
            await db.rollback()
            logger.exception(f"IntegrityError creating book: {e}")
            msg = "Book with similar details already exists"
            raise ValueError(msg) from e

        # Trigger automatic tagging
        try:
            tagging_service = TaggingService(db)

            # Build content preview
            content_preview = []
            if book.author:
                content_preview.append(f"Author: {book.author}")
            if book.description:
                # Take first 1000 characters
                desc_preview = book.description[:1000]
                if len(book.description) > 1000:
                    desc_preview += "..."
                content_preview.append(f"Description: {desc_preview}")

            # Generate and store tags
            tags = await tagging_service.tag_content(
                content_id=book.id,
                content_type="book",
                user_id=user_id,
                title=book.title,
                content_preview="\n\n".join(content_preview),
            )

            # Update book's tags field
            if tags:
                book.tags = json.dumps(tags)
                await db.commit()

            logger.info(f"Successfully tagged book {book.id} with tags: {tags}")

        except Exception as e:
            # Don't fail book creation if tagging fails
            logger.exception(f"Failed to tag book {book.id}: {e}")

        # Ensure book object is refreshed before validation
        await db.refresh(book)

        # Convert to dict first to avoid SQLAlchemy lazy loading issues
        return BookResponse.model_validate(self._book_to_dict(book))

    async def get_books(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> BookListResponse:
        """Get paginated list of books with optional filtering."""
        # Log the access
        self.log_access("list", user_id, "book")

        # Apply user filtering first
        query_builder = self.get_query_builder(Book)
        base_query = select(Book)
        query = query_builder.apply_user_filter(base_query, user_id)

        # Apply filters
        filters = []
        if search:
            filters.append(
                or_(
                    Book.title.ilike(f"%{search}%"),
                    Book.author.ilike(f"%{search}%"),
                    Book.description.ilike(f"%{search}%"),
                ),
            )

        if tags:
            # Filter by tags (stored as JSON)
            filters.extend(Book.tags.ilike(f"%{tag}%") for tag in tags)

        if filters:
            query = query.where(*filters)

        # Order by created_at desc by default
        query = query.order_by(Book.created_at.desc())

        # Paginate
        paginator = Paginator(page=page, limit=size)
        items, total = await paginator.paginate(db, query)

        # Convert to response format
        book_responses = [BookResponse.model_validate(self._book_to_dict(item)) for item in items]

        # Calculate pages
        pages = (total + size - 1) // size if size > 0 else 0

        return BookListResponse(
            items=book_responses,
            total=total,
            page=page,
            pages=pages,
        )

    async def get_book(self, db: AsyncSession, book_id: str, user_id: UUID) -> BookResponse:
        """Get a single book by UUID."""
        # Log the access
        self.log_access("get", user_id, "book", book_id)

        # Convert string UUID to UUID object
        book_id_obj = parse_book_id(book_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Book)
        base_query = select(Book).where(Book.id == book_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        book = result.scalar_one_or_none()

        if not book:
            msg = f"Book with ID {book_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(book, user_id):
            msg = f"Book with ID {book_id} not found"
            raise ValueError(msg)

        return BookResponse.model_validate(self._book_to_dict(book))

    async def update_book(self, db: AsyncSession, book_id: str, update_data: BookUpdate, user_id: UUID) -> BookResponse:
        """Update book metadata."""
        # Log the access
        self.log_access("update", user_id, "book", book_id)

        # Convert string UUID to UUID object
        book_id_obj = parse_book_id(book_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Book)
        base_query = select(Book).where(Book.id == book_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        book = result.scalar_one_or_none()

        if not book:
            msg = f"Book with ID {book_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(book, user_id):
            msg = f"Book with ID {book_id} not found"
            raise ValueError(msg)

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)

        # Handle tags serialization
        if "tags" in update_dict and update_dict["tags"] is not None:
            update_dict["tags"] = json.dumps(update_dict["tags"])

        # Handle table_of_contents serialization
        if "table_of_contents" in update_dict and update_dict["table_of_contents"] is not None:
            update_dict["table_of_contents"] = json.dumps(update_dict["table_of_contents"])

        for field, value in update_dict.items():
            setattr(book, field, value)

        book.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(book)

        return BookResponse.model_validate(self._book_to_dict(book))

    async def delete_book(self, db: AsyncSession, book_id: str, user_id: UUID) -> None:
        """Delete a book."""
        # Log the access
        self.log_access("delete", user_id, "book", book_id)

        # Convert string UUID to UUID object
        book_id_obj = parse_book_id(book_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Book)
        base_query = select(Book).where(Book.id == book_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        book = result.scalar_one_or_none()

        if not book:
            msg = f"Book with ID {book_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(book, user_id):
            msg = f"Book with ID {book_id} not found"
            raise ValueError(msg)

        # Store file path before deletion
        file_path = book.file_path

        # Delete the book
        await db.delete(book)
        await db.commit()

        # Delete file from storage
        if file_path:
            try:
                storage = get_storage_provider()
                await storage.delete(file_path)
                logger.info(f"Deleted book file from storage: {file_path}")
            except Exception as e:
                # Log error but don't fail the deletion
                logger.exception(f"Failed to delete file from storage: {e}")

    async def search_books(
        self,
        query: str,
        user_id: UUID,
        filters: dict[str, Any] | None = None
    ) -> list[BookResponse]:
        """Search books with filters."""
        async with async_session_maker() as db:
            # Use get_books with search parameter
            result = await self.get_books(
                db=db,
                user_id=user_id,
                search=query,
                tags=filters.get("tags") if filters else None,
                page=1,
                size=50  # Reasonable limit for search results
            )
            return result.items

    async def get_user_books(self, user_id: UUID) -> list[BookResponse]:
        """Get all books for a user."""
        async with async_session_maker() as db:
            # Use get_books without filters to get all books
            result = await self.get_books(
                db=db,
                user_id=user_id,
                page=1,
                size=1000  # Large limit to get all books
            )
            return result.items

    async def get_book_chapters(self, db: AsyncSession, book_id: str, user_id: UUID) -> list[dict]:
        """Get chapters/table of contents for a book."""
        # Convert string UUID to UUID object
        book_id_obj = parse_book_id(book_id)

        # Get the book with user filtering (following video service pattern)
        query_builder = self.get_query_builder(Book)
        base_query = select(Book).where(Book.id == book_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        book = result.scalar_one_or_none()

        if not book:
            # Check if book exists without user filter
            unfiltered_result = await db.execute(select(Book).where(Book.id == book_id_obj))
            unfiltered_book = unfiltered_result.scalar_one_or_none()

            if unfiltered_book:
                logger.warning(f"Book {book_id} exists but user {user_id} does not have access")
                msg = f"Book with ID {book_id} not found"
                raise ValueError(msg)

            return []

        # Parse table of contents
        if book.table_of_contents:
            try:
                toc_data = json.loads(book.table_of_contents)
                if isinstance(toc_data, list):
                    return toc_data
            except (json.JSONDecodeError, TypeError):
                pass

        return []

    async def extract_and_update_toc(
        self,
        db: AsyncSession,
        book_id: str,
        user_id: UUID
    ) -> BookResponse:
        """Extract and update table of contents for a book."""
        # Get the book
        return await self.get_book(db, book_id, user_id)

        # TODO: Implement actual TOC extraction logic
        # For now, just return the book as-is



# Service instance
book_service = BookService()
