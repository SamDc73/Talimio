"""Books module facade."""

import json
import logging
import uuid
from typing import cast

from fastapi import BackgroundTasks, status
from pydantic import JsonValue
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.service import RAGService
from src.books.models import Book
from src.books.schemas import (
    MEDIA_TYPES,
    BookFileType,
    BookLearningStatus,
    BookProgressResponse,
    BookProgressUpdate,
    BookRagStatus,
    BookResponse,
    BookTocChapterResponse,
    BookWithProgress,
)
from src.database.session import async_session_maker
from src.exceptions import ConflictError, DomainError, ErrorCategory, ErrorCode, NotFoundError, ValidationError
from src.storage.factory import get_storage_provider

from .services.book_content_service import BookContentService
from .services.book_metadata_service import BookMetadata, BookMetadataExtractionError, BookMetadataService
from .services.book_progress_service import BookProgressService
from .services.book_response_builder import BookResponseBuilder


logger = logging.getLogger(__name__)
BOOK_RESOURCE_TYPE = "book"
BOOK_RAG_STATUS_PENDING: BookRagStatus = "pending"
BOOK_RAG_STATUS_PROCESSING: BookRagStatus = "processing"
BOOK_RAG_STATUS_COMPLETED: BookRagStatus = "completed"
BOOK_RAG_STATUS_FAILED: BookRagStatus = "failed"
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


class BooksFacadeInternalError(DomainError):
    """Raised when book workflows fail with internal processing errors."""

    category = ErrorCategory.INTERNAL
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    default_error_code = ErrorCode.INTERNAL

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area="books")


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


def _apply_completed_chapters(chapters: list[dict[str, JsonValue]], completed_chapters: dict[str, bool]) -> None:
    """Annotate nested table-of-contents items with completion state."""
    for chapter in chapters:
        chapter_id = chapter.get("id")
        if chapter_id is not None:
            chapter["completed"] = completed_chapters.get(str(chapter_id), False)

        children = chapter.get("children")
        if isinstance(children, list):
            child_items = [child for child in children if isinstance(child, dict)]
            _apply_completed_chapters(child_items, completed_chapters)


def _find_chapter(chapters: list[BookTocChapterResponse], chapter_id: str) -> BookTocChapterResponse | None:
    """Return the nested chapter that matches the given id."""
    for chapter in chapters:
        if chapter.id == chapter_id:
            return chapter
        nested_match = _find_chapter(chapter.children, chapter_id)
        if nested_match is not None:
            return nested_match
    return None


class BooksFacade:
    """Single entry point for all book operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._content_service = BookContentService(session)
        self._progress_service = BookProgressService(session)

    async def _require_owned_book(self, *, book_id: uuid.UUID, user_id: uuid.UUID, operation: str) -> Book:
        result = await self._session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
        book = result.scalar_one_or_none()
        if book is None:
            logger.warning(
                "BOOK_ACCESS_DENIED",
                extra={"user_id": str(user_id), "book_id": str(book_id), "operation": operation},
            )
            raise NotFoundError(BOOK_RESOURCE_TYPE, str(book_id))
        return book

    async def get_content_with_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        """Get book content with progress for cross-module progress contracts."""
        book_with = await self.get_book(content_id, user_id)

        try:
            progress = await self._progress_service.get_progress(content_id, user_id)
        except (RuntimeError, ValueError):
            progress = None

        return {
            "book": book_with.model_dump(),
            "progress": progress or {},
            "completion_percentage": (progress or {}).get("completion_percentage", 0),
        }

    async def get_book(
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> BookWithProgress:
        """Get a single book with progress as a typed response."""
        try:
            book = await self._require_owned_book(book_id=book_id, user_id=user_id, operation="get_book")
            progress_payload = await self._progress_service.get_progress(book_id, user_id)
            progress = BookResponseBuilder.build_progress_response(progress_payload, book_id) if progress_payload else None
            return BookResponseBuilder.build_book_with_progress(book, progress)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, TypeError) as error:
            logger.exception(
                "books.get.failed",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error_type": type(error).__name__},
            )
            message = "Failed to retrieve book"
            raise BooksFacadeInternalError(message) from error

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

    async def extract_book_metadata_background(self, book_id: uuid.UUID) -> None:
        """Download the uploaded file once and persist page count + table of contents.

        Runs in a dedicated short-lived session so request transactions stay short.
        Uses the single ``storage.download(key)`` primitive that all providers
        implement (local/R2/GCS), so the same code path works identically across
        every backend with zero branching.

        Idempotent: only fills empty fields, so re-scheduling on a book that
        already has metadata is a no-op and re-running after partial failure is safe.
        """
        async with async_session_maker() as session:
            book = await session.get(Book, book_id)
            if book is None or not book.file_path:
                return

            storage = get_storage_provider(book.storage_provider)
            try:
                content = await storage.download(book.file_path)
            except (OSError, RuntimeError, ValueError):
                logger.exception("books.metadata.download_failed", extra={"book_id": str(book_id)})
                return

            if not content:
                logger.warning("books.metadata.empty_content", extra={"book_id": str(book_id)})
                return

            try:
                metadata = BookMetadataService().extract_metadata(content, f".{book.file_type}")
            except BookMetadataExtractionError:
                logger.exception("books.metadata.extract_failed", extra={"book_id": str(book_id)})
                return

            updated = False
            if metadata.total_pages and not book.total_pages:
                book.total_pages = metadata.total_pages
                updated = True
            if metadata.table_of_contents and not book.table_of_contents:
                book.table_of_contents = json.dumps(metadata.table_of_contents)
                updated = True
            if metadata.publication_year and not book.publication_year:
                book.publication_year = metadata.publication_year
                updated = True
            if metadata.language and not book.language:
                book.language = metadata.language
                updated = True
            if metadata.isbn and not book.isbn:
                book.isbn = metadata.isbn
                updated = True

            if not updated:
                return

            try:
                await session.commit()
                logger.info(
                    "books.metadata.extracted",
                    extra={
                        "book_id": str(book_id),
                        "total_pages": book.total_pages,
                        "toc_entries": len(metadata.table_of_contents or []),
                    },
                )
            except SQLAlchemyError:
                logger.exception("books.metadata.commit_failed", extra={"book_id": str(book_id)})

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
        storage_provider: str,
        title: str,
        metadata: dict[str, JsonValue] | None = None,
    ) -> tuple[BookResponse, uuid.UUID]:
        """Upload a book file to the user's library and return the created response."""
        try:
            data: dict[str, JsonValue] = {**(metadata or {})}
            data["title"] = title or data.get("title")
            data["file_path"] = file_path
            data["storage_provider"] = storage_provider
            data.setdefault("rag_status", "pending")

            book = await self._content_service.create_book(data, user_id)
            book_id = getattr(book, "id", None)
            if not isinstance(book_id, uuid.UUID):
                message = "Uploaded book did not receive an ID"
                raise TypeError(message)

            total_pages = getattr(book, "total_pages", 0)
            try:
                await self._progress_service.initialize_progress(book_id, user_id, total_pages=total_pages)
            except (RuntimeError, TypeError, ValueError) as error:
                logger.warning(
                    "Failed to initialize progress tracking",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(error)},
                )

            refreshed_book = await self._session.get(Book, book_id, populate_existing=True)
            if refreshed_book is not None:
                book = refreshed_book

            return BookResponseBuilder.build_book_response(book), book_id
        except ConflictError:
            raise
        except IntegrityError as error:
            constraint_name: str | None = None
            original_error = getattr(error, "orig", None)
            diag = getattr(original_error, "diag", None) if original_error is not None else None
            if diag is not None:
                constraint_name = getattr(diag, "constraint_name", None)

            if constraint_name == "books_user_id_file_hash_key":
                logger.info("BOOK_UPLOAD_DUPLICATE_FILE", extra={"user_id": str(user_id), "title": title})
                message = "This file already exists in your library"
                raise ConflictError(message) from error

            logger.exception("books.upload.integrity_error", extra={"user_id": str(user_id)})
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError):
            logger.exception("books.upload.failed", extra={"user_id": str(user_id), "title": title})
            raise

    async def create_book_from_existing_storage(
        self,
        *,
        user_id: uuid.UUID,
        filename: str,
        file_path: str,
        storage_provider: str,
        title: str,
        file_size: int | None = None,
        author: str | None = None,
        subtitle: str | None = None,
        description: str | None = None,
        isbn: str | None = None,
        language: str | None = None,
        publication_year: int | None = None,
        publisher: str | None = None,
        tags: list[str] | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> BookResponse:
        """Create a book record after a browser-direct upload completes."""
        expected_prefix = f"books/{user_id!s}/direct/"
        if not file_path.startswith(expected_prefix):
            message = "Uploaded file path does not belong to this user"
            raise ValidationError(message)

        storage = get_storage_provider(storage_provider)

        file_extension = filename.lower().split(".")[-1]
        if file_extension not in MEDIA_TYPES:
            message = "Unsupported book file type"
            raise ValidationError(message)
        file_type = cast("BookFileType", file_extension)
        if file_size is None or file_size <= 0:
            message = "file_size is required for direct upload finalization"
            raise ValidationError(message)
        metadata = BookMetadata(file_type=file_type)
        resolved_file_size = file_size
        file_hash = None

        filename_without_ext = filename.rsplit(".", 1)[0]
        final_title = metadata.title if metadata.title and (not title or title == filename_without_ext) else title
        final_author = author.strip() if author and author.strip() else ""
        if metadata.author and not final_author:
            final_author = metadata.author

        book_metadata: dict[str, JsonValue] = {
            "title": final_title,
            "subtitle": subtitle or metadata.subtitle,
            "author": final_author,
            "description": description or metadata.description,
            "isbn": isbn or metadata.isbn,
            "language": language or metadata.language,
            "publication_year": publication_year or metadata.publication_year,
            "publisher": publisher or metadata.publisher,
            "tags": tags or [],
            "file_type": file_type,
            "file_size": resolved_file_size,
            "total_pages": metadata.total_pages or 0,
            "file_hash": file_hash,
            "table_of_contents": json.dumps(metadata.table_of_contents) if metadata.table_of_contents else None,
        }

        try:
            book_response, book_id = await self.upload_book(
                user_id=user_id,
                file_path=file_path,
                storage_provider=storage_provider,
                title=final_title,
                metadata=book_metadata,
            )
        except (ConflictError, NotFoundError, ValidationError, SQLAlchemyError, RuntimeError, ValueError, TypeError):
            try:
                await storage.delete(file_path)
            except (OSError, RuntimeError, ValueError):
                logger.exception(
                    "books.direct_upload.rollback_file_delete_failed",
                    extra={"user_id": str(user_id), "storage_key": file_path},
                )
                raise
            raise

        if background_tasks is not None:
            await self._session.commit()
            background_tasks.add_task(self.extract_book_metadata_background, book_id)
            background_tasks.add_task(self.embed_book_background, book_id)
            background_tasks.add_task(self.auto_tag_book_background, book_id, user_id)

        return book_response

    async def update_progress(
        self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, JsonValue]
    ) -> dict[str, object]:
        """Update book reading progress."""
        await self._require_owned_book(book_id=content_id, user_id=user_id, operation="update_progress")
        try:
            updated_progress = await self._progress_service.update_progress(content_id, user_id, dict(progress_data))
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception(
                "Error updating progress",
                extra={"user_id": str(user_id), "book_id": str(content_id), "error": str(error)},
            )
            raise

        return {"progress": updated_progress}

    async def update_progress_from_request(
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
        progress_data: BookProgressUpdate,
    ) -> BookProgressResponse:
        """Map an API progress request into the canonical book progress response."""
        progress_dict = self._build_progress_dict(progress_data)
        result = await self.update_progress(book_id, user_id, progress_dict)
        progress = result.get("progress", {})
        progress_payload = cast("dict[str, object]", progress) if isinstance(progress, dict) else {}
        return BookResponseBuilder.build_progress_response(progress_payload, book_id)

    @staticmethod
    def _build_progress_dict(progress_data: BookProgressUpdate) -> dict[str, JsonValue]:
        """Build the service progress payload from an update request."""
        progress_dict: dict[str, JsonValue] = {}

        if (
            progress_data.total_pages is not None
            and progress_data.current_page is not None
            and progress_data.current_page > progress_data.total_pages
        ):
            message = "current_page cannot exceed total_pages"
            raise ValidationError(message)

        if progress_data.current_page is not None:
            progress_dict["page"] = progress_data.current_page
        if progress_data.total_pages is not None:
            progress_dict["total_pages"] = progress_data.total_pages
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

    async def update_book(self, book_id: uuid.UUID, user_id: uuid.UUID, update_data: dict[str, JsonValue]) -> BookResponse:
        """Update book metadata."""
        try:
            book = await self._content_service.update_book(book_id, dict(update_data), user_id)
            return BookResponse.model_validate(book)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception(
                "Error updating book",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(error)},
            )
            raise

    async def get_book_chapters(self, book_id: uuid.UUID, user_id: uuid.UUID) -> list[BookTocChapterResponse]:
        """Get book chapters or table-of-contents items for a book."""
        try:
            book = await self._require_owned_book(book_id=book_id, user_id=user_id, operation="get_chapters")

            chapters: list[dict[str, JsonValue]] = []
            if isinstance(book.table_of_contents, str) and book.table_of_contents:
                try:
                    parsed_toc = json.loads(book.table_of_contents)
                    if isinstance(parsed_toc, list):
                        chapters = [chapter for chapter in parsed_toc if isinstance(chapter, dict)]
                except (json.JSONDecodeError, TypeError):
                    chapters = []

            if chapters:
                progress = await self._progress_service.get_progress(book_id, user_id)
                completed_chapters = progress.get("toc_progress", {})
                if isinstance(completed_chapters, dict):
                    _apply_completed_chapters(chapters, cast("dict[str, bool]", completed_chapters))

            return [BookTocChapterResponse.model_validate(chapter) for chapter in chapters]
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception(
                "Error getting chapters",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(error)},
            )
            raise

    async def update_book_chapter_status(
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_id: str,
        status: BookLearningStatus,
    ) -> BookTocChapterResponse:
        """Update chapter status and return canonical chapter payload."""
        completed = status == "completed"
        await self.mark_chapter_complete(book_id, user_id, chapter_id, completed)

        chapters = await self.get_book_chapters(book_id, user_id)
        chapter = _find_chapter(chapters, chapter_id)
        if chapter is not None:
            return chapter

        message = f"Updated chapter {chapter_id} was not found in book {book_id}"
        raise NotFoundError(message=message)

    async def get_book_rag_status_payload(self, book_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        """Get RAG status payload for a book owned by a user."""
        book = await self._require_owned_book(book_id=book_id, user_id=user_id, operation="get_rag_status")

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
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
        chapter_id: str,
        completed: bool = True,
    ) -> None:
        """Mark a book chapter as completed."""
        await self._require_owned_book(book_id=book_id, user_id=user_id, operation="mark_chapter_complete")
        try:
            await self._progress_service.mark_chapter_complete(book_id, user_id, chapter_id, completed)
        except NotFoundError:
            raise
        except (SQLAlchemyError, RuntimeError, ValueError, TypeError) as error:
            logger.exception(
                "Error marking chapter complete",
                extra={
                    "user_id": str(user_id),
                    "book_id": str(book_id),
                    "chapter_id": chapter_id,
                    "error": str(error),
                },
            )
            raise
