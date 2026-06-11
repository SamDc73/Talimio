"""Procrastinate tasks for course outline and lesson content generation.

These wrap the generation job bodies in ``src.courses.services.generation_jobs``.
Each task runs the LLM in a short-lived dedicated session and retries on bad
model output so a single malformed JSON response never surfaces to the user.
"""

from __future__ import annotations

import logging
import uuid
from typing import cast

import procrastinate

from src.jobs.app import QUEUE_GENERATION, job_app


logger = logging.getLogger(__name__)


@job_app.task(
    name="generation.generate_course_outline",
    queue=QUEUE_GENERATION,
    retry=procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def generate_course_outline(
    course_id: str,
    user_id: str,
    image_data_urls: list[str] | None = None,
    book_ids: list[str] | None = None,
) -> None:
    """Generate a course outline out-of-request and eager-enqueue its lesson content."""
    from src.courses.services.generation_jobs import run_course_outline_generation

    await run_course_outline_generation(
        course_id=uuid.UUID(course_id),
        user_id=uuid.UUID(user_id),
        image_data_urls=list(image_data_urls or []),
        book_ids=[uuid.UUID(book_id) for book_id in (book_ids or [])],
    )
    logger.info("jobs.course_outline.done", extra={"course_id": course_id, "user_id": user_id})


@job_app.task(
    name="generation.generate_lesson_version",
    queue=QUEUE_GENERATION,
    retry=procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def generate_lesson_version(
    version_id: str,
    user_id: str,
    generation_mode: str,
    source_version_id: str | None = None,
    critique_text: str | None = None,
    force: bool = False,
) -> None:
    """Fill one pending lesson version with generated content out-of-request."""
    from src.courses.services.generation_jobs import LessonGenerationMode, run_lesson_version_generation

    mode: LessonGenerationMode = "first_pass"
    if generation_mode in {"first_pass", "regeneration", "adaptive_revisit_pass"}:
        mode = cast("LessonGenerationMode", generation_mode)

    await run_lesson_version_generation(
        version_id=uuid.UUID(version_id),
        user_id=uuid.UUID(user_id),
        generation_mode=mode,
        source_version_id=uuid.UUID(source_version_id) if source_version_id else None,
        critique_text=critique_text,
        force=force,
    )
    logger.info(
        "jobs.lesson_version.done",
        extra={"lesson_version_id": version_id, "user_id": user_id, "generation_mode": generation_mode},
    )
