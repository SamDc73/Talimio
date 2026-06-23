import json
import uuid
from typing import cast

from pydantic import JsonValue, ValidationError as PydanticValidationError
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.courses.models import Course, Lesson
from src.exceptions import NotFoundError, ValidationError
from src.videos.models import Video

from .models import Highlight
from .schemas import HighlightResponse
from .validation import validate_highlight_data


CONTENT_TYPE_BOOK = "book"
CONTENT_TYPE_VIDEO = "video"
CONTENT_TYPE_LESSON = "lesson"
RESOURCE_TYPE_HIGHLIGHT = "highlight"

# Generic highlights allow extra location fields, so cap the stored blob. A real selection
# plus its position data stays well under this; the limit only blocks pathological payloads.
MAX_HIGHLIGHT_DATA_BYTES = 64 * 1024


def _validated_payload(payload: dict[str, object], content_type: str) -> dict[str, object]:
    """Normalize a highlight payload through the content-type validation schemas."""
    try:
        data = cast("dict[str, JsonValue]", payload)
        validated = validate_highlight_data(data, content_type)
    except PydanticValidationError as error:
        message = f"Invalid highlight data: {error!s}"
        raise ValidationError(message, feature_area="highlights") from error

    if len(json.dumps(validated)) > MAX_HIGHLIGHT_DATA_BYTES:
        message = f"Highlight data exceeds the {MAX_HIGHLIGHT_DATA_BYTES} byte limit"
        raise ValidationError(message, feature_area="highlights")
    return validated


class HighlightService:
    """Manage highlights for owned books, videos, and lessons."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_book_highlights(self, book_id: uuid.UUID, user_id: uuid.UUID) -> list[HighlightResponse]:
        """Return every highlight for an owned book."""
        await self._require_book(book_id, user_id)
        return await self._list_highlights(CONTENT_TYPE_BOOK, book_id, user_id)

    async def create_book_highlight(
        self, book_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, object]
    ) -> HighlightResponse:
        """Create a highlight for an owned book."""
        await self._require_book(book_id, user_id)
        return await self._create_highlight(CONTENT_TYPE_BOOK, book_id, user_id, payload)

    async def list_video_highlights(self, video_id: uuid.UUID, user_id: uuid.UUID) -> list[HighlightResponse]:
        """Return every highlight for an owned video."""
        await self._require_video(video_id, user_id)
        return await self._list_highlights(CONTENT_TYPE_VIDEO, video_id, user_id)

    async def create_video_highlight(
        self, video_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, object]
    ) -> HighlightResponse:
        """Create a highlight for an owned video."""
        await self._require_video(video_id, user_id)
        return await self._create_highlight(CONTENT_TYPE_VIDEO, video_id, user_id, payload)

    async def list_lesson_highlights(
        self, course_id: uuid.UUID, lesson_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[HighlightResponse]:
        """Return every highlight for an owned lesson."""
        await self._require_lesson(course_id, lesson_id, user_id)
        return await self._list_highlights(CONTENT_TYPE_LESSON, lesson_id, user_id)

    async def create_lesson_highlight(
        self, course_id: uuid.UUID, lesson_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, object]
    ) -> HighlightResponse:
        """Create a highlight for an owned lesson."""
        await self._require_lesson(course_id, lesson_id, user_id)
        return await self._create_highlight(CONTENT_TYPE_LESSON, lesson_id, user_id, payload)

    async def update_highlight(
        self, highlight_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, object]
    ) -> HighlightResponse:
        """Update one owned highlight, re-validating against its stored content type."""
        highlight = await self._require_highlight(highlight_id, user_id)
        highlight.highlight_data = _validated_payload(payload, highlight.content_type)
        await self._session.flush()
        await self._session.refresh(highlight)
        return HighlightResponse.model_validate(highlight)

    async def delete_highlight(self, highlight_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete one owned highlight."""
        highlight = await self._require_highlight(highlight_id, user_id)
        await self._session.delete(highlight)
        await self._session.flush()

    async def _create_highlight(
        self, content_type: str, content_id: uuid.UUID, user_id: uuid.UUID, payload: dict[str, object]
    ) -> HighlightResponse:
        highlight = Highlight(
            user_id=user_id,
            content_type=content_type,
            content_id=content_id,
            highlight_data=_validated_payload(payload, content_type),
        )
        self._session.add(highlight)
        await self._session.flush()
        await self._session.refresh(highlight)
        return HighlightResponse.model_validate(highlight)

    async def _list_highlights(
        self, content_type: str, content_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[HighlightResponse]:
        result = await self._session.execute(
            select(Highlight)
            .where(
                and_(
                    Highlight.user_id == user_id,
                    Highlight.content_type == content_type,
                    Highlight.content_id == content_id,
                )
            )
            .order_by(Highlight.created_at.desc())
        )
        return [HighlightResponse.model_validate(highlight) for highlight in result.scalars().all()]

    async def _require_book(self, book_id: uuid.UUID, user_id: uuid.UUID) -> None:
        book = await self._session.scalar(select(Book).where(Book.id == book_id, Book.user_id == user_id))
        if book is None:
            raise NotFoundError(CONTENT_TYPE_BOOK, str(book_id), feature_area="highlights")

    async def _require_video(self, video_id: uuid.UUID, user_id: uuid.UUID) -> None:
        video = await self._session.scalar(select(Video).where(Video.id == video_id, Video.user_id == user_id))
        if video is None:
            raise NotFoundError(CONTENT_TYPE_VIDEO, str(video_id), feature_area="highlights")

    async def _require_lesson(self, course_id: uuid.UUID, lesson_id: uuid.UUID, user_id: uuid.UUID) -> None:
        lesson = await self._session.scalar(
            select(Lesson)
            .join(Course, Lesson.course_id == Course.id)
            .where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
                Course.user_id == user_id,
            )
        )
        if lesson is None:
            raise NotFoundError(CONTENT_TYPE_LESSON, str(lesson_id), feature_area="highlights")

    async def _require_highlight(self, highlight_id: uuid.UUID, user_id: uuid.UUID) -> Highlight:
        highlight = await self._session.scalar(
            select(Highlight).where(Highlight.id == highlight_id, Highlight.user_id == user_id)
        )
        if highlight is None:
            raise NotFoundError(RESOURCE_TYPE_HIGHLIGHT, str(highlight_id), feature_area="highlights")
        return highlight
