"""Book query service for complex database operations."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auth.config import DEFAULT_USER_ID
from src.books.models import Book, BookProgress
from src.books.schemas import BookListResponse, BookResponse, BookWithProgress
from src.books.services.book_response_builder import BookResponseBuilder


logger = logging.getLogger(__name__)


class BookQueryService:
    """Service for complex book database queries and operations."""

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the book query service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id or DEFAULT_USER_ID

    async def get_books_paginated(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        tags: list[str] | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> BookListResponse:
        """Get books with pagination, filtering, and sorting.

        Args:
            page: Page number (1-based)
            per_page: Number of books per page
            search: Search term for title/author filtering
            tags: List of tags to filter by
            sort_by: Field to sort by
            sort_order: Sort order (asc/desc)

        Returns
        -------
            BookListResponse: Paginated book list with metadata
        """
        # Build base query
        query = select(Book)

        # Apply search filter
        if search:
            search_term = f"%{search}%"
            query = query.where(
                Book.title.ilike(search_term) | Book.author.ilike(search_term) | Book.description.ilike(search_term)
            )

        # Apply tag filter
        if tags:
            for tag in tags:
                tag_pattern = f'%"{tag}"%'
                query = query.where(Book.tags.ilike(tag_pattern))

        # Get total count for pagination
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        # Apply sorting
        sort_column = getattr(Book, sort_by, Book.created_at)
        if sort_order.lower() == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        offset = (page - 1) * per_page
        query = query.offset(offset).limit(per_page)

        # Execute query
        result = await self.session.execute(query)
        books = result.scalars().all()

        # Convert to response objects
        book_responses = BookResponseBuilder.build_book_list(books)

        return BookListResponse(
            items=book_responses,
            total=total,
            page=page,
            pages=(total + per_page - 1) // per_page,
        )

    async def get_book_with_progress(self, book_id: UUID) -> BookWithProgress | None:
        """Get a book by ID with progress information.

        Args:
            book_id: Book ID

        Returns
        -------
            BookWithProgress: Book data with progress or None if not found
        """
        query = select(Book).options(selectinload(Book.progress_records)).where(Book.id == book_id)
        result = await self.session.execute(query)
        book = result.scalar_one_or_none()

        if not book:
            return None

        # Get progress for user
        progress = None
        for prog in book.progress_records:
            if prog.user_id == self.user_id:
                progress = prog
                break

        return BookResponseBuilder.build_book_with_progress(book, progress)

    async def search_books(
        self,
        query_text: str,
        limit: int = 20,
        include_content: bool = False,
    ) -> list[BookResponse]:
        """Search books by text across multiple fields.

        Args:
            query_text: Search query
            limit: Maximum number of results
            include_content: Whether to search in book content (future feature)

        Returns
        -------
            List of matching books
        """
        _ = include_content
        search_term = f"%{query_text}%"

        # Search across title, author, description, and tags
        query = (
            select(Book)
            .where(
                Book.title.ilike(search_term)
                | Book.author.ilike(search_term)
                | Book.description.ilike(search_term)
                | Book.tags.ilike(search_term)
            )
            .limit(limit)
        )

        result = await self.session.execute(query)
        books = result.scalars().all()

        return BookResponseBuilder.build_book_list(books)

    async def get_books_by_tags(self, tags: list[str], operator: str = "AND") -> list[BookResponse]:
        """Get books that match specified tags.

        Args:
            tags: List of tags to filter by
            operator: "AND" (all tags) or "OR" (any tag)

        Returns
        -------
            List of matching books
        """
        query = select(Book)

        if operator.upper() == "AND":
            # All tags must be present
            for tag in tags:
                tag_pattern = f'%"{tag}"%'
                query = query.where(Book.tags.ilike(tag_pattern))
        else:
            # Any tag can be present (OR)
            tag_conditions = []
            for tag in tags:
                tag_pattern = f'%"{tag}"%'
                tag_conditions.append(Book.tags.ilike(tag_pattern))

            if tag_conditions:
                from sqlalchemy import or_

                query = query.where(or_(*tag_conditions))

        result = await self.session.execute(query)
        books = result.scalars().all()

        return BookResponseBuilder.build_book_list(books)

    async def get_recently_read_books(self, limit: int = 10) -> list[BookResponse]:
        """Get recently read books for the current user.

        Args:
            limit: Maximum number of books to return

        Returns
        -------
            List of recently read books
        """
        query = (
            select(Book)
            .join(BookProgress, Book.id == BookProgress.book_id)
            .where(BookProgress.user_id == self.user_id)
            .where(BookProgress.last_read_at.is_not(None))
            .order_by(BookProgress.last_read_at.desc())
            .limit(limit)
        )

        result = await self.session.execute(query)
        books = result.scalars().all()

        return BookResponseBuilder.build_book_list(books)

    async def get_books_by_reading_status(
        self,
        status: str,
        limit: int | None = None,
    ) -> list[BookResponse]:
        """Get books by reading status.

        Args:
            status: Reading status ("not_started", "in_progress", "completed")
            limit: Maximum number of books to return

        Returns
        -------
            List of books with specified status
        """
        # Map status to progress conditions
        if status == "not_started":
            # No progress record exists or progress is 0
            subquery = select(BookProgress.book_id).where(
                BookProgress.user_id == self.user_id,
                BookProgress.progress_percentage > 0,
            )
            query = select(Book).where(Book.id.not_in(subquery))
        elif status == "completed":
            # Progress is 100%
            query = (
                select(Book)
                .join(BookProgress, Book.id == BookProgress.book_id)
                .where(BookProgress.user_id == self.user_id)
                .where(BookProgress.progress_percentage >= 100)
            )
        else:  # in_progress
            # Progress exists and is between 1-99%
            query = (
                select(Book)
                .join(BookProgress, Book.id == BookProgress.book_id)
                .where(BookProgress.user_id == self.user_id)
                .where(BookProgress.progress_percentage > 0)
                .where(BookProgress.progress_percentage < 100)
            )

        if limit:
            query = query.limit(limit)

        result = await self.session.execute(query)
        books = result.scalars().all()

        return BookResponseBuilder.build_book_list(books)

    async def get_book_stats(self) -> dict[str, Any]:
        """Get statistics about books in the library.

        Returns
        -------
            Dictionary with various book statistics
        """
        # Total books
        total_query = select(func.count(Book.id))
        total_result = await self.session.execute(total_query)
        total_books = total_result.scalar() or 0

        # Books with progress
        progress_query = select(func.count(func.distinct(BookProgress.book_id))).where(
            BookProgress.user_id == self.user_id
        )
        progress_result = await self.session.execute(progress_query)
        books_with_progress = progress_result.scalar() or 0

        # Completed books
        completed_query = select(func.count(BookProgress.book_id)).where(
            BookProgress.user_id == self.user_id,
            BookProgress.progress_percentage >= 100,
        )
        completed_result = await self.session.execute(completed_query)
        completed_books = completed_result.scalar() or 0

        # Average progress
        avg_query = select(func.avg(BookProgress.progress_percentage)).where(
            BookProgress.user_id == self.user_id,
            BookProgress.progress_percentage > 0,
        )
        avg_result = await self.session.execute(avg_query)
        avg_progress = avg_result.scalar() or 0

        return {
            "total_books": total_books,
            "books_with_progress": books_with_progress,
            "completed_books": completed_books,
            "in_progress_books": books_with_progress - completed_books,
            "not_started_books": total_books - books_with_progress,
            "average_progress": round(float(avg_progress), 2) if avg_progress else 0,
            "completion_rate": round((completed_books / total_books) * 100, 2) if total_books and total_books > 0 else 0,
        }


# Removed _book_to_response - now handled by BookResponseBuilder
