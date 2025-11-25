"""Book response builder service for consistent response formatting."""

import json
import logging
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from src.books.models import Book
from src.books.schemas import (
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

        payload: dict[str, Any] = {
            "id": book.id,
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
            "rag_status": book.rag_status,
            "rag_processed_at": book.rag_processed_at,
            "table_of_contents": toc_list,
            "created_at": book.created_at,
            "updated_at": book.updated_at,
        }

        return BookResponse.model_validate(payload)

    @staticmethod
    def build_book_with_progress(book: Book, progress: BookProgressResponse | None = None) -> BookWithProgress:
        """Convert Book model to BookWithProgress with optional progress."""
        book_response = BookResponseBuilder.build_book_response(book)

        progress_response = progress if progress else None
        payload = book_response.model_dump()
        payload["progress"] = progress_response

        return BookWithProgress.model_validate(payload)

    @staticmethod
    def build_progress_response(progress: Mapping[str, Any], book_id: UUID) -> BookProgressResponse:
        """Convert a progress dictionary into a BookProgressResponse."""
        current_page = progress.get("page", progress.get("current_page", 1)) or 1
        if isinstance(current_page, (int, float)) and current_page < 1:
            current_page = 1

        total_pages_read = progress.get("total_pages_read", progress.get("page", 1)) or current_page
        if isinstance(total_pages_read, (int, float)) and total_pages_read < 1:
            total_pages_read = current_page

        progress_percentage = progress.get("completion_percentage", 0) or 0
        if isinstance(progress_percentage, (int, float)):
            progress_percentage = max(0, min(100, progress_percentage))

        payload: dict[str, Any] = {
            "id": progress.get("id"),
            "book_id": book_id,
            "current_page": current_page,
            "progress_percentage": progress_percentage,
            "total_pages_read": total_pages_read,
            "reading_time_minutes": progress.get("reading_time_minutes", 0),
            "status": progress.get("status", "not_started"),
            "notes": progress.get("notes"),
            "bookmarks": progress.get("bookmarks", []),
            "toc_progress": progress.get("toc_progress", {}),
            "last_read_at": progress.get("last_accessed_at", progress.get("last_read_at")),
            "created_at": progress.get("created_at"),
            "updated_at": progress.get("updated_at"),
        }

        return BookProgressResponse.model_validate(payload)

    @staticmethod
    def build_book_list(books: list[Book]) -> list[BookResponse]:
        """Convert list of Book models to list of BookResponse."""
        return [BookResponseBuilder.build_book_response(book) for book in books]

    @staticmethod
    def _convert_toc_to_schema(toc_data: list[dict]) -> list[TableOfContentsItem]:
        """Convert table of contents data to schema objects."""
        result = []
        for item in toc_data:
            children = []
            if item.get("children"):
                children = BookResponseBuilder._convert_toc_to_schema(item["children"])

            toc_payload: dict[str, Any] = {
                "id": item.get("id", ""),
                "title": item.get("title", ""),
                "page": item.get("page"),
                "start_page": item.get("start_page"),
                "end_page": item.get("end_page"),
                "level": item.get("level", 0),
                "children": children,
            }
            toc_item = TableOfContentsItem.model_validate(toc_payload)
            result.append(toc_item)
        return result
