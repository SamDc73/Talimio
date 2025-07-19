"""
Compatibility module that re-exports functions for the router.

This provides backward compatibility while the router is updated.
"""

from .services.book_service import (
    batch_update_chapter_statuses,
    create_book,
    extract_and_create_chapters,
    extract_and_update_toc,
    get_book_chapter,
    get_book_chapters,
    update_book_chapter_status,
    update_book_progress,
)


__all__ = [
    "batch_update_chapter_statuses",
    "create_book",
    "extract_and_create_chapters",
    "extract_and_update_toc",
    "get_book_chapter",
    "get_book_chapters",
    "update_book_chapter_status",
    "update_book_progress",
]
