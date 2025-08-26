"""Book response builder service for consistent response formatting."""

import json
import logging
from typing import Any

from src.books.models import Book, BookChapter, BookProgress
from src.books.schemas import (
    BookChapterResponse,
    BookProgressResponse,
    BookResponse,
    BookWithProgress,
    TableOfContentsItem,
)


logger = logging.getLogger(__name__)


class BookResponseBuilder:
    """Service for building consistent book responses and serialization."""

    @staticmethod
    def build_book_response(book: Book) -> BookResponse:
        """Convert Book model to BookResponse with proper handling."""
        # Handle tags
        tags_list = []
        if book.tags:
            try:
                tags_list = json.loads(book.tags)
            except (json.JSONDecodeError, TypeError):
                tags_list = []

        # Handle table of contents
        toc_list = None
        if book.table_of_contents:
            try:
                toc_data = json.loads(book.table_of_contents)
                if isinstance(toc_data, list):
                    toc_list = BookResponseBuilder._convert_toc_to_schema(toc_data)
            except (json.JSONDecodeError, TypeError):
                toc_list = None

        return BookResponse(
            id=book.id,
            title=book.title,
            subtitle=book.subtitle,
            author=book.author,
            description=book.description,
            isbn=book.isbn,
            language=book.language,
            publication_year=book.publication_year,
            publisher=book.publisher,
            tags=tags_list,
            file_path=book.file_path,
            file_type=book.file_type,
            file_size=book.file_size,
            total_pages=book.total_pages,
            rag_status=book.rag_status,
            rag_processed_at=book.rag_processed_at,
            table_of_contents=toc_list,
            created_at=book.created_at,
            updated_at=book.updated_at,
        )

    @staticmethod
    def build_book_with_progress(book: Book, progress: BookProgress | None = None) -> BookWithProgress:
        """Convert Book model to BookWithProgress with optional progress."""
        book_response = BookResponseBuilder.build_book_response(book)

        progress_response = None
        if progress:
            progress_response = BookProgressResponse.model_validate(progress)

        return BookWithProgress(
            id=book_response.id,
            title=book_response.title,
            subtitle=book_response.subtitle,
            author=book_response.author,
            description=book_response.description,
            isbn=book_response.isbn,
            language=book_response.language,
            publication_year=book_response.publication_year,
            publisher=book_response.publisher,
            tags=book_response.tags,
            file_path=book_response.file_path,
            file_type=book_response.file_type,
            file_size=book_response.file_size,
            total_pages=book_response.total_pages,
            rag_status=book_response.rag_status,
            rag_processed_at=book_response.rag_processed_at,
            table_of_contents=book_response.table_of_contents,
            created_at=book_response.created_at,
            updated_at=book_response.updated_at,
            progress=progress_response,
        )

    @staticmethod
    def build_chapter_response(chapter: BookChapter) -> BookChapterResponse:
        """Convert BookChapter model to BookChapterResponse."""
        return BookChapterResponse.model_validate(chapter)

    @staticmethod
    def build_progress_response(progress: BookProgress) -> BookProgressResponse:
        """Convert BookProgress model to BookProgressResponse."""
        return BookProgressResponse.model_validate(progress)

    @staticmethod
    def build_book_list(books: list[Book]) -> list[BookResponse]:
        """Convert list of Book models to list of BookResponse."""
        return [BookResponseBuilder.build_book_response(book) for book in books]

    @staticmethod
    def build_chapter_list(chapters: list[BookChapter]) -> list[BookChapterResponse]:
        """Convert list of BookChapter models to list of BookChapterResponse."""
        return [BookResponseBuilder.build_chapter_response(chapter) for chapter in chapters]

    @staticmethod
    def _convert_toc_to_schema(toc_data: list[dict]) -> list[TableOfContentsItem]:
        """Convert table of contents data to schema objects."""
        result = []
        for item in toc_data:
            children = []
            if item.get("children"):
                children = BookResponseBuilder._convert_toc_to_schema(item["children"])

            toc_item = TableOfContentsItem(
                id=item.get("id", ""),
                title=item.get("title", ""),
                page=item.get("page"),
                start_page=item.get("start_page"),
                end_page=item.get("end_page"),
                level=item.get("level", 0),
                children=children,
            )
            result.append(toc_item)
        return result

    @staticmethod
    def serialize_tags(tags: list[str]) -> str:
        """Serialize tags list to JSON string."""
        return json.dumps(tags)

    @staticmethod
    def deserialize_tags(tags_json: str | None) -> list[str]:
        """Deserialize tags from JSON string."""
        if not tags_json:
            return []
        try:
            return json.loads(tags_json)
        except (json.JSONDecodeError, TypeError):
            return []

    @staticmethod
    def serialize_toc(toc: list[dict] | None) -> str | None:
        """Serialize table of contents to JSON string."""
        if not toc:
            return None
        try:
            return json.dumps(toc)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def deserialize_toc(toc_json: str | None) -> list[dict] | None:
        """Deserialize table of contents from JSON string."""
        if not toc_json:
            return None
        try:
            return json.loads(toc_json)
        except (json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def build_error_response(
        error_code: str, error_message: str, details: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Build consistent error response format."""
        response = {
            "error": error_code,
            "message": error_message,
            "timestamp": None,  # This would be set by the framework
        }
        if details:
            response["details"] = details
        return response

    @staticmethod
    def build_success_response(data: Any, message: str | None = None) -> dict[str, Any]:
        """Build consistent success response format."""
        response = {
            "success": True,
            "data": data,
        }
        if message:
            response["message"] = message
        return response
