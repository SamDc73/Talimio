import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.exceptions import NotFoundError

from .models import Highlight
from .schemas import HighlightResponse


BOOK_RESOURCE_TYPE = "book"
HIGHLIGHT_RESOURCE_TYPE = "highlight"


class BookHighlightService:
    """Manage highlights for owned books."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_highlights(self, book_id: uuid.UUID, user_id: uuid.UUID) -> list[HighlightResponse]:
        """Return every highlight for an owned book."""
        await self._require_book(book_id, user_id)
        result = await self._session.execute(
            select(Highlight).where(
                and_(
                    Highlight.user_id == user_id,
                    Highlight.content_type == "book",
                    Highlight.content_id == book_id,
                )
            )
        )
        return [HighlightResponse.model_validate(highlight) for highlight in result.scalars().all()]

    async def create_highlight(
        self,
        book_id: uuid.UUID,
        user_id: uuid.UUID,
        highlight_data: dict[str, object],
    ) -> HighlightResponse:
        """Create a highlight for an owned book."""
        await self._require_book(book_id, user_id)

        highlight = Highlight(
            user_id=user_id,
            content_type="book",
            content_id=book_id,
            highlight_data=highlight_data,
        )
        self._session.add(highlight)
        await self._session.flush()
        await self._session.refresh(highlight)
        return HighlightResponse.model_validate(highlight)

    async def update_highlight(
        self,
        highlight_id: uuid.UUID,
        user_id: uuid.UUID,
        highlight_data: dict[str, object],
    ) -> HighlightResponse:
        """Update one owned highlight."""
        highlight = await self._require_highlight(highlight_id, user_id)
        highlight.highlight_data = highlight_data
        await self._session.flush()
        await self._session.refresh(highlight)
        return HighlightResponse.model_validate(highlight)

    async def delete_highlight(self, highlight_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete one owned highlight."""
        highlight = await self._require_highlight(highlight_id, user_id)
        await self._session.delete(highlight)
        await self._session.flush()

    async def _require_book(self, book_id: uuid.UUID, user_id: uuid.UUID) -> Book:
        book = await self._session.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
        if book is None:
            raise NotFoundError(BOOK_RESOURCE_TYPE, str(book_id), feature_area="highlights")
        return book

    async def _require_highlight(self, highlight_id: uuid.UUID, user_id: uuid.UUID) -> Highlight:
        highlight = await self._session.scalar(
            select(Highlight).where(
                Highlight.id == highlight_id,
                Highlight.user_id == user_id,
            )
        )
        if highlight is None:
            raise NotFoundError(HIGHLIGHT_RESOURCE_TYPE, str(highlight_id), feature_area="highlights")
        return highlight
