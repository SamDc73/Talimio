"""Course attachment link management: list, bulk attach, detach."""

import logging
import uuid
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.books.models import Book
from src.courses.models import Course, CourseAttachment
from src.courses.schemas import CourseAttachmentRead
from src.exceptions import NotFoundError


logger = logging.getLogger(__name__)


class CourseAttachmentsService:
    """Owns the course-to-book link rows. Never touches books or chunks."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_attachments(self, course_id: uuid.UUID, user_id: uuid.UUID) -> list[CourseAttachmentRead]:
        """Return all attachments for one owned course with book display fields."""
        await self._ensure_course_owned(course_id, user_id)
        return await self._query_attachments(course_id)

    async def attach_books(
        self,
        course_id: uuid.UUID,
        user_id: uuid.UUID,
        book_ids: Sequence[uuid.UUID],
    ) -> list[CourseAttachmentRead]:
        """Attach books to a course idempotently and return the full current list.

        Duplicates hit the UNIQUE constraint and are skipped via ON CONFLICT DO
        NOTHING. Archived books are attachable — archived is a listing concern.
        """
        await self._ensure_course_owned(course_id, user_id)
        unique_book_ids = list(dict.fromkeys(book_ids))
        await self._ensure_books_owned(unique_book_ids, user_id)

        if unique_book_ids:
            stmt = (
                insert(CourseAttachment)
                .values([{"course_id": course_id, "book_id": book_id} for book_id in unique_book_ids])
                .on_conflict_do_nothing(index_elements=[CourseAttachment.course_id, CourseAttachment.book_id])
            )
            await self._session.execute(stmt)
            await self._session.flush()

        logger.info(
            "courses.attachments.attached",
            extra={
                "course_id": str(course_id),
                "user_id": str(user_id),
                "book_ids": [str(book_id) for book_id in unique_book_ids],
            },
        )
        return await self._query_attachments(course_id)

    async def detach(self, course_id: uuid.UUID, attachment_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Delete one attachment row. The book and its chunks stay untouched."""
        await self._ensure_course_owned(course_id, user_id)
        result = await self._session.execute(
            delete(CourseAttachment).where(
                CourseAttachment.id == attachment_id,
                CourseAttachment.course_id == course_id,
            )
        )
        if int(getattr(result, "rowcount", 0) or 0) == 0:
            resource_type = "attachment"
            raise NotFoundError(resource_type, str(attachment_id))
        await self._session.flush()
        logger.info(
            "courses.attachments.detached",
            extra={
                "course_id": str(course_id),
                "user_id": str(user_id),
                "attachment_id": str(attachment_id),
            },
        )

    async def _query_attachments(self, course_id: uuid.UUID) -> list[CourseAttachmentRead]:
        rows = (
            await self._session.execute(
                select(CourseAttachment, Book)
                .join(Book, Book.id == CourseAttachment.book_id)
                .where(CourseAttachment.course_id == course_id)
                .order_by(CourseAttachment.created_at.asc(), CourseAttachment.id.asc())
            )
        ).all()
        return [
            CourseAttachmentRead(
                id=attachment.id,
                book_id=book.id,
                title=book.title,
                rag_status=book.rag_status,
                archived=book.archived,
                created_at=attachment.created_at,
            )
            for attachment, book in rows
        ]

    async def _ensure_course_owned(self, course_id: uuid.UUID, user_id: uuid.UUID) -> None:
        course_exists = await self._session.scalar(
            select(Course.id).where(Course.id == course_id, Course.user_id == user_id)
        )
        if course_exists is None:
            resource_type = "course"
            raise NotFoundError(resource_type, str(course_id))

    async def _ensure_books_owned(self, book_ids: Sequence[uuid.UUID], user_id: uuid.UUID) -> None:
        if not book_ids:
            return
        result = await self._session.execute(
            select(Book.id).where(Book.user_id == user_id, Book.id.in_(book_ids))
        )
        owned_ids = set(result.scalars().all())
        resource_type = "book"
        for book_id in book_ids:
            if book_id not in owned_ids:
                raise NotFoundError(resource_type, str(book_id))
