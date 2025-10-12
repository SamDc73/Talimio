"""Books Module Facade.

Single entry point for all book-related operations.
Coordinates internal book services and provides stable API for other modules.
"""

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.books.schemas import BookProgressResponse, BookResponse, BookWithProgress

from .services.book_content_service import BookContentService
from .services.book_progress_service import BookProgressService


logger = logging.getLogger(__name__)


class BooksFacade:
    """
    Single entry point for all book operations.

    Coordinates internal book services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self, session: AsyncSession, user_id: UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id
        # Internal services - initialized with session and user_id
        self._content_service = BookContentService(session, user_id)
        self._progress_service = BookProgressService(session, user_id)

    async def get_book(self, book_id: UUID) -> BookWithProgress:
        """Get a single book with progress as a typed response.

        Uses builder for the book and recalculates progress via BookProgressService to ensure accuracy.
        """
        try:
            # Ownership-checked book
            result = await self.session.execute(
                select(Book).where(Book.id == book_id, Book.user_id == self.user_id)
            )
            book = result.scalar_one_or_none()

            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(self.user_id), "book_id": str(book_id), "operation": "get_book"}
                )
                msg = "Book not found"
                raise ValueError(msg)

            # Build base book response
            base = BookResponse.model_validate(book)

            # Recalculate progress using the unified service (ToC-aware)
            prog = await self._progress_service.get_progress(book_id)
            progress = BookProgressResponse(
                id=prog.get("id"),
                book_id=book_id,
                current_page=prog.get("page", prog.get("current_page", 1)),
                progress_percentage=prog.get("completion_percentage", 0.0),
                total_pages_read=prog.get("total_pages_read", prog.get("page", 1)),
                reading_time_minutes=prog.get("reading_time_minutes", 0),
                status=prog.get("status", "not_started"),
                notes=prog.get("notes"),
                bookmarks=prog.get("bookmarks", []),
                toc_progress=prog.get("toc_progress", {}),
                last_read_at=prog.get("last_accessed_at", prog.get("last_read_at")),
                created_at=prog.get("created_at"),
                updated_at=prog.get("updated_at"),
            ) if prog else None

            return BookWithProgress(
                id=base.id,
                title=base.title,
                subtitle=base.subtitle,
                author=base.author,
                description=base.description,
                isbn=base.isbn,
                language=base.language,
                publication_year=base.publication_year,
                publisher=base.publisher,
                tags=base.tags,
                file_type=base.file_type,
                file_path=base.file_path,
                file_size=base.file_size,
                total_pages=base.total_pages,
                table_of_contents=base.table_of_contents,
                rag_status=base.rag_status,
                rag_processed_at=base.rag_processed_at,
                created_at=base.created_at,
                updated_at=base.updated_at,
                progress=progress,
            )

        except ValueError:
            raise
        except Exception as e:
            logger.exception(
                "Error getting book",
                extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
            )
            raise


    async def upload_book(
        self, file_path: str, title: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Upload book file to user's library.

        Handles file upload, format detection, and metadata extraction.
        """
        try:
            # Build book data combining provided metadata and required fields
            data: dict[str, Any] = {**(metadata or {})}
            data["title"] = title or data.get("title")
            data["file_path"] = file_path
            # Ensure RAG status set to pending for processing pipeline
            data.setdefault("rag_status", "pending")

            # Create the book record via content service
            book = await self._content_service.create_book(data)

            book_id = getattr(book, "id", None)
            total_pages = getattr(book, "total_pages", 0)

            # Auto-tag the created book (align with video flow)
            try:
                if book_id:
                    await self._auto_tag_book(book_id)
            except Exception as e:
                logger.warning(
                    "Automatic tagging failed",
                    extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
                )

            # Initialize progress tracking (non-fatal on failure)
            try:
                if book_id:
                    await self._progress_service.initialize_progress(book_id, total_pages=total_pages)
            except Exception as e:
                logger.warning(
                    "Failed to initialize progress tracking",
                    extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
                )

            # Ensure fully-loaded instance after all commits to avoid lazy refresh in response serialization
            try:
                if book_id:
                    fresh = await self.session.get(Book, book_id)
                    if fresh is not None:
                        await self.session.refresh(fresh)
                        book = fresh
            except Exception:
                # Non-fatal: proceed with existing instance
                logger.debug("Could not refresh book after upload", exc_info=True)

            return {"book": book, "success": True}

        except Exception as e:
            logger.exception(
                "Error uploading book",
                extra={"user_id": str(self.user_id), "title": title, "error": str(e)}
            )
            return {"error": f"Failed to upload book: {e!s}", "success": False}

    async def _auto_tag_book(self, book_id: UUID) -> list[str]:
        """Generate tags for a book using its content preview and store them.

        This mirrors the video auto-tagging flow: extract a content preview, call TaggingService,
        then persist generated tags to the Book.tags JSON field. Failures are logged but not raised.
        """
        try:
            # Defer imports to avoid circular dependencies and keep facade lightweight
            from src.books.models import Book
            from src.tagging.processors.book_processor import process_book_for_tagging
            from src.tagging.service import TaggingService

            # Extract content preview for tagging
            content_data = await process_book_for_tagging(str(book_id), self.session)
            if not content_data:
                logger.warning(
                    "Book not found or no content data for tagging",
                    extra={"user_id": str(self.user_id), "book_id": str(book_id)}
                )
                return []

            # Generate tags via TaggingService
            tagging_service = TaggingService(self.session)
            tags = await tagging_service.tag_content(
                content_id=book_id,
                content_type="book",
                user_id=self.user_id,
                title=content_data.get("title", ""),
                content_preview=content_data.get("content_preview", ""),
            )

            # Persist tags onto the Book model for backward compatibility
            if tags:
                db_book = await self.session.get(Book, book_id)
                if db_book:
                    db_book.tags = json.dumps(tags)
                    await self.session.commit()
                    logger.info(
                        "Book tagged successfully",
                        extra={"user_id": str(self.user_id), "book_id": str(book_id), "tag_count": len(tags)}
                    )
            else:
                # Still commit any flushed tag associations inside TaggingService
                await self.session.commit()

            return tags or []

        except Exception as e:
            logger.exception(
                "Auto-tagging error",
                extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
            )
            return []

    async def update_book_progress(self, book_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update book reading progress.

        Handles progress updates, page tracking, and completion detection.
        """
        try:
            # Update progress using the progress tracker
            updated_progress = await self._progress_service.update_progress(book_id, progress_data)

            if "error" in updated_progress:
                return {"error": updated_progress["error"], "success": False}

            return {"progress": updated_progress, "success": True}

        except Exception as e:
            logger.exception(
                "Error updating progress",
                extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
            )
            return {"error": f"Failed to update progress: {e!s}", "success": False}



    async def update_book(self, book_id: UUID, update_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update book metadata.

        Updates book information and coordinates any needed reprocessing.
        """
        try:
            # Update through content service which handles tags and reprocessing
            book = await self._content_service.update_book(book_id, update_data)

            return {"book": book, "success": True}

        except Exception as e:
            logger.exception(
                "Error updating book",
                extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
            )
            return {"error": "Failed to update book", "success": False}

    async def delete_book(self, session: AsyncSession, book_id: UUID, user_id: UUID) -> None:
        """
        Delete book and all related data.

        Args:
            session: Database session
            book_id: Book ID to delete
            user_id: User ID for ownership validation

        Raises
        ------
            ValueError: If book not found or user doesn't own it
        """
        # Get book with user validation
        result = await session.execute(select(Book).where(Book.id == book_id, Book.user_id == user_id))
        book = result.scalar_one_or_none()

        if not book:
            msg = f"Book {book_id} not found"
            raise ValueError(msg)

        # Delete storage object if present (unified for pdf/epub)
        try:
            if getattr(book, "file_path", None):
                from src.storage.factory import get_storage_provider  # lazy import to avoid cycles

                storage = get_storage_provider()
                await storage.delete(book.file_path)
                logger.info(
                    "Book file deleted from storage",
                    extra={"user_id": str(user_id), "book_id": str(book_id), "path": book.file_path},
                )
        except Exception as e:
            # Non-fatal: continue DB cleanup
            logger.warning(
                "Failed to delete book file from storage",
                extra={"user_id": str(user_id), "book_id": str(book_id), "error": str(e)},
            )

        # Delete RAG chunks first
        from src.ai.rag.service import RAGService

        await RAGService.delete_chunks_by_doc_id(session, str(book.id), doc_type="book")

        # Delete unified progress (user_progress) for this user+book
        try:
            from sqlalchemy import text

            await session.execute(
                text("DELETE FROM user_progress WHERE user_id = :user_id AND content_id = :content_id"),
                {"user_id": str(user_id), "content_id": str(book.id)},
            )
            logger.info(
                "Deleted progress for book",
                extra={"user_id": str(user_id), "book_id": str(book.id)},
            )
        except Exception as e:
            logger.warning(
                "Failed to delete progress for book",
                extra={"user_id": str(user_id), "book_id": str(book.id), "error": str(e)},
            )

        # Delete tag associations for this user+book (no FK cascade exists)
        try:
            from sqlalchemy import and_, delete

            from src.tagging.models import TagAssociation

            await session.execute(
                delete(TagAssociation).where(
                    and_(
                        TagAssociation.content_id == book.id,
                        TagAssociation.content_type == "book",
                        TagAssociation.user_id == user_id,
                    )
                )
            )
            logger.info(
                "Deleted tag associations for book",
                extra={"user_id": str(user_id), "book_id": str(book.id)},
            )
        except Exception as e:
            logger.warning(
                "Failed to delete tag associations for book",
                extra={"user_id": str(user_id), "book_id": str(book.id), "error": str(e)},
            )

        # Delete the book (cascade handles related records)
        await session.delete(book)
        # Note: Commit is handled by the caller (router)


    async def get_user_books(self, include_progress: bool = True) -> dict[str, Any]:
        """
        Get all books for user.

        Optionally includes progress information.
        """
        try:
            # Fetch books for this user
            result = await self.session.execute(
                select(Book).where(Book.user_id == self.user_id).order_by(Book.created_at.desc())
            )
            books = list(result.scalars().all())

            # Convert to dict format and optionally add progress
            book_dicts: list[dict[str, Any]] = []
            for book in books:
                book_response = BookResponse.model_validate(book)
                bd = book_response.model_dump()
                if include_progress:
                    progress = await self._progress_service.get_progress(bd["id"])
                    bd["progress"] = progress
                book_dicts.append(bd)

            return {"books": book_dicts, "success": True}

        except Exception as e:
            logger.exception(
                "Error getting books",
                extra={"user_id": str(self.user_id), "error": str(e)}
            )
            return {"error": f"Failed to get books: {e!s}", "success": False}

    async def get_book_chapters(self, book_id: UUID) -> dict[str, Any]:
        """Get book chapters/table of contents if available."""
        try:
            # Fetch book to read table_of_contents JSON
            result = await self.session.execute(select(Book).where(Book.id == book_id, Book.user_id == self.user_id))
            book = result.scalar_one_or_none()
            if not book:
                logger.warning(
                    "BOOK_ACCESS_DENIED",
                    extra={"user_id": str(self.user_id), "book_id": str(book_id), "operation": "get_chapters"}
                )
                return {"error": f"Book {book_id} not found", "success": False}

            chapters: list[dict] = []
            if getattr(book, "table_of_contents", None):
                try:
                    toc = json.loads(book.table_of_contents)  # type: ignore[arg-type]
                    if isinstance(toc, list):
                        chapters = toc
                except (json.JSONDecodeError, TypeError):
                    chapters = []

            # Add progress information for each chapter
            if chapters:
                progress = await self._progress_service.get_progress(book_id)
                completed_chapters = progress.get("completed_chapters", {})
                for chapter in chapters:
                    chapter["completed"] = completed_chapters.get(chapter.get("id"), False)

            return {"chapters": chapters or [], "success": True}

        except Exception as e:
            logger.exception(
                "Error getting chapters",
                extra={"user_id": str(self.user_id), "book_id": str(book_id), "error": str(e)}
            )
            return {"error": "Failed to get chapters", "success": False}

    async def mark_chapter_complete(
        self, book_id: UUID, chapter_id: str, completed: bool = True
    ) -> dict[str, Any]:
        """Mark a book chapter as completed."""
        try:
            result = await self._progress_service.mark_chapter_complete(book_id, chapter_id, completed)

            return {"result": result, "success": True}

        except Exception as e:
            logger.exception(
                "Error marking chapter complete",
                extra={"user_id": str(self.user_id), "book_id": str(book_id), "chapter_id": chapter_id, "error": str(e)}
            )
            return {"error": "Failed to mark chapter complete", "success": False}



