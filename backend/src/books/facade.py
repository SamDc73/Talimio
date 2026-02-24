
"""Books Module Facade.

Single entry point for all book-related operations.
Coordinates internal book services and provides a stable API for other modules.
Session-bound: uses the injected AsyncSession for all operations.
"""

import hashlib
import json
import logging
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.ai.rag.service import RAGService
from src.books.models import Book
from src.books.schemas import (
    BookLearningStatus,
    BookListResponse,
    BookRagStatus,
    BookResponse,
    BookTocChapterResponse,
    BookWithProgress,
)
from src.database.session import async_session_maker
from src.exceptions import ResourceNotFoundError
from src.storage.factory import get_storage_provider

from .services.book_content_service import BookContentService
from .services.book_metadata_service import BookMetadata, BookMetadataExtractionError, BookMetadataService
from .services.book_progress_service import BookProgressService
from .services.book_response_builder import BookResponseBuilder


if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable, Coroutine

    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)
BOOK_RESOURCE_TYPE = "book"
BOOK_RAG_STATUS_PENDING: BookRagStatus = "pending"
BOOK_RAG_STATUS_PROCESSING: BookRagStatus = "processing"
BOOK_RAG_STATUS_COMPLETED: BookRagStatus = "completed"
BOOK_RAG_STATUS_FAILED: BookRagStatus = "failed"
BOOK_CHAPTERS_ERROR_CODE_NOT_FOUND = "book_not_found"
BOOK_RAG_CHUNK_COUNT_STATUSES: tuple[BookRagStatus, ...] = (
    BOOK_RAG_STATUS_COMPLETED,
    BOOK_RAG_STATUS_PROCESSING,
)
BOOK_RAG_STATUS_MESSAGES: dict[BookRagStatus, str] = {
    BOOK_RAG_STATUS_PENDING: "Book is ready to read! AI chat will be available once processing completes.",
    BOOK_RAG_STATUS_PROCESSING: "Book is being processed for AI chat. You can start reading now!",
    BOOK_RAG_STATUS_COMPLETED: "Book is ready! AI chat is now available.",
    BOOK_RAG_STATUS_FAILED: "Processing failed. AI chat is not available, but you can still read the book.",
}


def _parse_json_tags(raw_tags: str | None) -> list[str]:
    """Parse serialized tags JSON into a list."""
    if not raw_tags:
        return []
    try:
        parsed = json.loads(raw_tags)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [str(tag) for tag in parsed if isinstance(tag, str)]


def _merge_tags(existing_tags: list[str], generated_tags: list[str]) -> list[str]:
    """Merge existing and generated tags while keeping insertion order."""
    return list(dict.fromkeys([*existing_tags, *generated_tags]))


class BooksFacade:
    """
    Single entry point for all book operations.

    Coordinates internal book services, publishes events, and provides
    a stable API while sharing the request-scoped session.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._content_service = BookContentService(session)
        self._progress_service = BookProgressService(session)

    async def get_content_with_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Get book with progress in IntegrityErrora dict structure (parity with other facades)."""
        try:
            book_with = await self.get_book(content_id, user_id)
        except ResourceNotFoundError:
            return {"error": "Book not found", "success": False}

        # Also retrieve unified progress to ensure core fields are present
        try:
            progress = await self._progress_service.get_progress(content_id, user_id)
        except (RuntimeError, ValueError):
            progress = None

        return {
            "book": book_with.model_dump(),
            "progress": (progress or {}),
            "completion_percentage": (progress or {}).get("completion_percentage", 0),
            "success": True,
        }

    async def get_book(self, book_id: uuid.UUID, user_id: uuid.UUID) -> BookWithProgress:
        """Get a single book with progress as a typed response."""
        try:
            # Ownership-checked book
            result = await self._session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
            book = result.scalar_one_or_none()

            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "operation": "get_book"},
                )
                raise ResourceNotFoundError(BOOK_RESOURCE_TYPE, str(book_id))

            # Recalculate progress using the unified service (ToC-aware)
            prog = await self._progress_service.get_progress(book_id, user_id)
            progress = BookResponseBuilder.build_progress_response(prog, book_id) if prog else None

            return BookResponseBuilder.build_book_with_progress(book, progress)

        except ResourceNotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, TypeError) as e:
            logger.exception(
                "Error getting book",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
            )
            raise

    async def get_paginated_user_books(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> BookListResponse:
        """List books for a user with filtering and pagination."""
        result = await self.get_user_books(user_id, include_progress=True)
        if not result.get("success"):
            msg = str(result.get("error", "Failed to get books"))
            raise RuntimeError(msg)

        books = result.get("books", [])

        if search:
            search_lower = search.lower()
            books = [
                book
                for book in books
                if search_lower in (book.get("title") or "").lower()
                or search_lower in (book.get("author") or "").lower()
                or search_lower in (book.get("description") or "").lower()
            ]

        if tags:
            books = [book for book in books if any(tag in (book.get("tags") or []) for tag in tags)]

        total = len(books)
        start = (page - 1) * limit
        end = start + limit
        paginated_books = books[start:end]

        return BookListResponse(
            items=[BookResponse.model_validate(book) for book in paginated_books],
            total=total,
            page=page,
            pages=(total + limit - 1) // limit,
        )

    async def create_book_from_upload(
        self,
        user_id: uuid.UUID,
        filename: str,
        file_content: bytes,
        title: str,
        author: str | None = None,
        subtitle: str | None = None,
        description: str | None = None,
        isbn: str | None = None,
        language: str | None = None,
        publication_year: int | None = None,
        publisher: str | None = None,
        tags: list[str] | None = None,
        spawn_detached_task: Callable[[Coroutine[Any, Any, None]], None] | None = None,
        embed_book_background: Callable[[uuid.UUID], Coroutine[Any, Any, None]] | None = None,
        auto_tag_book_background: Callable[[uuid.UUID, uuid.UUID], Coroutine[Any, Any, None]] | None = None,
    ) -> dict[str, Any]:
        """Create a book from uploaded file bytes and metadata payload."""
        file_extension = filename.lower().split(".")[-1]
        storage_key = f"books/{user_id!s}/{filename}"

        storage = get_storage_provider()
        logger.info("Uploading file to storage: %s", storage_key)
        await storage.upload(file_content, storage_key)

        metadata_service = BookMetadataService()
        try:
            metadata = metadata_service.extract_metadata(file_content, f".{file_extension}")
        except BookMetadataExtractionError as error:
            logger.warning(
                "Metadata extraction failed for %s; continuing upload with fallback metadata: %s",
                filename,
                error,
            )
            metadata = BookMetadata(file_type=file_extension)
        logger.info(
            "Extracted metadata - title: %s, author: %s, pages: %s",
            metadata.title,
            metadata.author,
            metadata.total_pages,
        )

        file_hash = hashlib.sha256(file_content).hexdigest()
        filename_without_ext = filename.rsplit(".", 1)[0]

        final_title = title
        if metadata.title and (not title or title == filename_without_ext):
            final_title = metadata.title

        final_author = author
        if metadata.author and (not author or not author.strip()):
            final_author = metadata.author

        book_metadata = {
            "title": final_title,
            "subtitle": subtitle or metadata.subtitle,
            "author": final_author,
            "description": description or metadata.description,
            "isbn": isbn or metadata.isbn,
            "language": language or metadata.language,
            "publication_year": publication_year or metadata.publication_year,
            "publisher": publisher or metadata.publisher,
            "tags": tags or [],
            "file_type": file_extension,
            "file_size": len(file_content),
            "total_pages": metadata.total_pages or 0,
            "file_hash": file_hash,
            "table_of_contents": json.dumps(metadata.table_of_contents) if metadata.table_of_contents else None,
        }

        result = await self.upload_book(
            user_id=user_id,
            file_path=storage_key,
            title=final_title,
            metadata=book_metadata,
        )

        if not result.get("success"):
            with suppress(OSError, RuntimeError, ValueError):
                await storage.delete(storage_key)
            return {
                "error": result.get("error", "Failed to create book"),
                "error_code": result.get("error_code"),
                "success": False,
            }

        book_id = result.get("book_id")
        if (
            book_id
            and spawn_detached_task is not None
            and embed_book_background is not None
            and auto_tag_book_background is not None
        ):
            await self._session.commit()
            spawn_detached_task(embed_book_background(book_id))
            spawn_detached_task(auto_tag_book_background(book_id, user_id))

        book_response = result.get("book")
        if not isinstance(book_response, BookResponse):
            return {"error": "Failed to build book response", "success": False}

        return {"book": book_response, "success": True}

    async def embed_book_background(self, book_id: uuid.UUID) -> None:
        """Process embeddings for a book in a dedicated background session."""
        async with async_session_maker() as session:
            try:
                await RAGService().process_book(session, book_id)
                await session.commit()
            except (SQLAlchemyError, RuntimeError, ValueError):
                try:
                    await session.commit()
                except SQLAlchemyError:
                    logger.debug("Failed to commit failed RAG status for book %s", book_id, exc_info=True)
                logger.exception("Failed to embed book %s", book_id)

    async def auto_tag_book_background(self, book_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Generate and persist tags for a book in a dedicated background session."""
        try:
            from src.tagging.processors.book_processor import process_book_for_tagging
            from src.tagging.service import TaggingService, update_content_tags_json

            async with async_session_maker() as session:
                content_data = await process_book_for_tagging(book_id, user_id, session)
                if not content_data:
                    logger.warning("Skipping tagging for missing book %s", book_id)
                    return

                generated_tags = await TaggingService(session).tag_content(
                    content_id=book_id,
                    content_type="book",
                    user_id=user_id,
                    title=content_data.get("title", ""),
                    content_preview=content_data.get("content_preview", ""),
                )

                book = await session.get(Book, book_id)
                if book is None:
                    logger.warning("Skipping tag JSON update for missing book %s", book_id)
                    return

                merged_tags = _merge_tags(_parse_json_tags(book.tags), generated_tags)
                await update_content_tags_json(
                    session=session,
                    content_id=book_id,
                    content_type="book",
                    tags=merged_tags,
                    user_id=user_id,
                )
                await session.commit()
                logger.info("Successfully tagged book %s with tags: %s", book_id, generated_tags)
        except (SQLAlchemyError, RuntimeError, ValueError, OSError):
            logger.exception("Failed to tag book %s", book_id)

    async def upload_book(
        self,
        user_id: uuid.UUID,
        file_path: str,
        title: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Upload book file to user's library."""
        try:
            # Build book data combining provided metadata and required fields
            data: dict[str, Any] = {**(metadata or {})}
            data["title"] = title or data.get("title")
            data["file_path"] = file_path
            # Ensure RAG status set to pending for processing pipeline
            data.setdefault("rag_status", "pending")

            # Create the book record via content service (prefer request session when provided)
            book = await self._content_service.create_book(data, user_id)

            book_id = getattr(book, "id", None)
            total_pages = getattr(book, "total_pages", 0)

            # Initialize progress tracking (non-fatal on failure)
            try:
                if book_id:
                    await self._progress_service.initialize_progress(book_id, user_id, total_pages=total_pages)
            except (RuntimeError, TypeError, ValueError) as e:
                logger.warning(
                    "Failed to initialize progress tracking",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
                )

            # Reload from DB so we return a stable snapshot even if other operations used rollbacks/commits.
            if book_id:
                refreshed_book = await self._session.get(Book, book_id, populate_existing=True)
                if refreshed_book:
                    book = refreshed_book

            return {
                "book": BookResponseBuilder.build_book_response(book),
                "book_id": book_id,
                "success": True,
            }

        except IntegrityError as e:
            # Most common conflict is a duplicate file in the same user's library.
            # Keep this sanitized so we don't leak SQL internals to clients.
            constraint_name: str | None = None
            orig = getattr(e, "orig", None)
            diag = getattr(orig, "diag", None) if orig is not None else None
            if diag is not None:
                constraint_name = getattr(diag, "constraint_name", None)

            if constraint_name == "books_user_id_file_hash_key":
                logger.info(
                    "BOOK_UPLOAD_DUPLICATE_FILE",
                    extra={"user_id": str(user_id), "title": title},
                )
                return {
                    "error": "Duplicate file upload",
                    "error_code": "duplicate_file",
                    "success": False,
                }

            logger.exception("Book upload failed due to integrity error", extra={"user_id": str(user_id)})
            return {"error": "Failed to upload book", "success": False}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Error uploading book", extra={"user_id": str(user_id), "title": title, "error": str(e)})
            return {"error": f"Failed to upload book: {e!s}", "success": False}

    async def update_progress(self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update book reading progress."""
        try:
            # Update progress using the progress tracker
            updated_progress = await self._progress_service.update_progress(content_id, user_id, progress_data)

            if "error" in updated_progress:
                return {"error": updated_progress["error"], "success": False}

            return {"progress": updated_progress, "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception(
                "Error updating progress",
                extra={"user_id": str(user_id), "book_id": str(content_id), "error": str(e)},
            )
            return {"error": f"Failed to update progress: {e!s}", "success": False}

    async def update_book(self, book_id: uuid.UUID, user_id: uuid.UUID, update_data: dict[str, Any]) -> dict[str, Any]:
        """Update book metadata."""
        try:
            # Update through content service which handles tags and reprocessing
            book = await self._content_service.update_book(book_id, update_data, user_id)

            return {"book": book, "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception(
                "Error updating book", extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)}
            )
            return {"error": "Failed to update book", "success": False}

    async def get_user_books(self, user_id: uuid.UUID, include_progress: bool = True) -> dict[str, Any]:
        """Get all books for user. Optionally includes progress information."""
        try:
            # Fetch books for this user
            result = await self._session.execute(
                select(Book).where(Book.user_id == user_id).order_by(Book.created_at.desc())
            )
            books = list(result.scalars().all())

            # Convert to dict format and optionally add progress
            book_dicts: list[dict[str, Any]] = []
            for book in books:
                book_response = BookResponse.model_validate(book)
                bd = book_response.model_dump()
                if include_progress:
                    progress = await self._progress_service.get_progress(bd["id"], user_id)
                    bd["progress"] = progress
                book_dicts.append(bd)

            return {"books": book_dicts, "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception("Error getting books", extra={"user_id": str(user_id), "error": str(e)})
            return {"error": f"Failed to get books: {e!s}", "success": False}

    async def get_book_chapters(self, book_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Get book chapters/table of contents if available."""
        try:
            # Fetch book to read table_of_contents JSON
            result = await self._session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
            book = result.scalar_one_or_none()
            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "operation": "get_chapters"},
                )
                return {
                    "error": f"Book {book_id} not found",
                    "error_code": BOOK_CHAPTERS_ERROR_CODE_NOT_FOUND,
                    "success": False,
                }

            chapters: list[dict] = []
            table_of_contents = book.table_of_contents
            if isinstance(table_of_contents, str) and table_of_contents:
                try:
                    toc = json.loads(table_of_contents)
                    if isinstance(toc, list):
                        chapters = toc
                except (json.JSONDecodeError, TypeError):
                    chapters = []

            # Add progress information for each chapter
            if chapters:
                progress = await self._progress_service.get_progress(book_id, user_id)
                completed_chapters = progress.get("completed_chapters", {})
                for chapter in chapters:
                    chapter["completed"] = completed_chapters.get(chapter.get("id"), False)

            return {"chapters": chapters or [], "success": True}

        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception(
                "Error getting chapters",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
            )
            return {"error": "Failed to get chapters", "success": False}

    async def update_book_chapter_status(
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_id: str,
        status: BookLearningStatus,
    ) -> BookTocChapterResponse:
        """Update chapter status and return canonical chapter payload."""
        completed = status == "completed"
        result = await self.mark_chapter_complete(book_id, user_id, chapter_id, completed)
        if not result.get("success"):
            msg = str(result.get("error", "Failed to update chapter status"))
            raise RuntimeError(msg)

        chapters_result = await self.get_book_chapters(book_id, user_id)
        if not chapters_result.get("success"):
            error_code = chapters_result.get("error_code")
            if error_code == BOOK_CHAPTERS_ERROR_CODE_NOT_FOUND:
                raise ResourceNotFoundError(BOOK_RESOURCE_TYPE, str(book_id))
            msg = str(chapters_result.get("error", "Failed to load updated chapter data"))
            raise RuntimeError(msg)

        raw_chapters = chapters_result.get("chapters", [])
        for raw_chapter in raw_chapters:
            if str(raw_chapter.get("id", "")) == chapter_id:
                return BookTocChapterResponse.model_validate(raw_chapter)

        msg = f"Updated chapter {chapter_id} was not found in book {book_id}"
        raise RuntimeError(msg)

    async def get_book_rag_status_payload(self, book_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """Get RAG status payload for a book owned by a user."""
        result = await self._session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
        book = result.scalar_one_or_none()
        if not book:
            raise ResourceNotFoundError(BOOK_RESOURCE_TYPE, str(book_id))

        chunk_count = None
        if book.rag_status in BOOK_RAG_CHUNK_COUNT_STATUSES:
            try:
                count_result = await self._session.execute(
                    text("SELECT COUNT(*) FROM rag_document_chunks WHERE doc_id = :doc_id"),
                    {"doc_id": str(book_id)},
                )
                chunk_count = count_result.scalar()
            except SQLAlchemyError:
                logger.debug("Could not count RAG chunks")

        error_details = None
        if book.rag_status == BOOK_RAG_STATUS_FAILED and hasattr(book, "rag_error"):
            error_details = getattr(book, "rag_error", None)

        return {
            "book_id": book_id,
            "rag_status": book.rag_status,
            "rag_processed_at": book.rag_processed_at.isoformat() if book.rag_processed_at else None,
            "message": BOOK_RAG_STATUS_MESSAGES.get(book.rag_status, "Unknown status"),
            "chunk_count": chunk_count,
            "error_details": error_details,
        }

    async def mark_chapter_complete(
        self, book_id: uuid.UUID, user_id: uuid.UUID, chapter_id: str, completed: bool = True
    ) -> dict[str, Any]:
        """Mark a book chapter as completed."""
        try:
            await self._progress_service.mark_chapter_complete(book_id, user_id, chapter_id, completed)
            return {"result": True, "success": True}
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as e:
            logger.exception(
                "Error marking chapter complete",
                extra={
                    "user_id": str(user_id),
                    "book_id": str(book_id),
                    "chapter_id": chapter_id,
                    "error": str(e),
                },
            )
            return {"error": "Failed to mark chapter complete", "success": False}
