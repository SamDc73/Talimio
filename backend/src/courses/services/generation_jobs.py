"""Enqueue helpers and job bodies for out-of-request course and lesson generation.

HTTP handlers write a row in a ``generating`` state and ``defer_*`` a procrastinate
job keyed to that artifact; the worker runs the LLM in a short-lived dedicated
session and flips the row to ``ready`` or ``failed``. Reads never call the LLM —
they enqueue idempotently as a safety net (the queueing lock collapses duplicates).
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import async_session_maker
from src.jobs import (
    QUEUE_GENERATION,
    course_outline_queueing_lock,
    defer_job,
    lesson_version_queueing_lock,
)


logger = logging.getLogger(__name__)

COURSE_OUTLINE_TASK_NAME = "generation.generate_course_outline"
LESSON_VERSION_TASK_NAME = "generation.generate_lesson_version"
COURSE_OUTLINE_JOB_PRIORITY = 10

LessonGenerationMode = Literal["first_pass", "regeneration", "adaptive_revisit_pass"]


async def defer_course_outline_generation(
    session: AsyncSession,
    *,
    course_id: uuid.UUID,
    user_id: uuid.UUID,
    image_data_urls: list[str],
    book_ids: list[uuid.UUID],
) -> int | None:
    """Enqueue course outline generation inside the caller's transaction."""
    return await defer_job(
        session,
        task_name=COURSE_OUTLINE_TASK_NAME,
        queue=QUEUE_GENERATION,
        args={
            "course_id": str(course_id),
            "user_id": str(user_id),
            "image_data_urls": list(image_data_urls),
            "book_ids": [str(book_id) for book_id in book_ids],
        },
        queueing_lock=course_outline_queueing_lock(course_id),
        priority=COURSE_OUTLINE_JOB_PRIORITY,
    )


async def defer_lesson_version_generation(
    session: AsyncSession,
    *,
    version_id: uuid.UUID,
    user_id: uuid.UUID,
    generation_mode: LessonGenerationMode,
    source_version_id: uuid.UUID | None = None,
    critique_text: str | None = None,
    force: bool = False,
) -> int | None:
    """Enqueue lesson-version content generation inside the caller's transaction."""
    return await defer_job(
        session,
        task_name=LESSON_VERSION_TASK_NAME,
        queue=QUEUE_GENERATION,
        args={
            "version_id": str(version_id),
            "user_id": str(user_id),
            "generation_mode": generation_mode,
            "source_version_id": str(source_version_id) if source_version_id else None,
            "critique_text": critique_text,
            "force": force,
        },
        queueing_lock=lesson_version_queueing_lock(version_id),
    )


async def run_course_outline_generation(
    *,
    course_id: uuid.UUID,
    user_id: uuid.UUID,
    image_data_urls: list[str],
    book_ids: list[uuid.UUID],
) -> None:
    """Job body: build a course outline in a dedicated session, then eager-enqueue lesson content."""
    from src.courses.services.course_content_service import CourseContentService

    async with async_session_maker() as session:
        service = CourseContentService(session)
        await service.run_outline_generation_job(
            course_id=course_id,
            user_id=user_id,
            image_data_urls=image_data_urls,
            book_ids=book_ids,
        )


async def run_lesson_version_generation(
    *,
    version_id: uuid.UUID,
    user_id: uuid.UUID,
    generation_mode: LessonGenerationMode,
    source_version_id: uuid.UUID | None,
    critique_text: str | None,
    force: bool,
) -> None:
    """Job body: fill one pending lesson version with generated content in a dedicated session."""
    from src.courses.services.lesson_service import LessonService

    async with async_session_maker() as session:
        service = LessonService(session, user_id)
        await service.run_lesson_version_generation_job(
            version_id=version_id,
            generation_mode=generation_mode,
            source_version_id=source_version_id,
            critique_text=critique_text,
            force=force,
        )
