"""Books services module."""

from .book_progress_service import BookProgressService
from .book_query_service import BookQueryService
from .book_service import BookService, delete_book, get_book, get_books, update_book
from .highlight_service import HighlightService
from .interface import IBookService


__all__ = [
    "BookProgressService",
    "BookQueryService",
    "BookService",
    "HighlightService",
    "IBookService",
    "delete_book",
    "get_book",
    "get_books",
    "update_book",
]
