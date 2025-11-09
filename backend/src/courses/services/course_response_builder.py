"""Course response builder service for constructing course responses."""

from __future__ import annotations

import contextlib
import json
from collections import defaultdict
from collections.abc import Iterable
from typing import TYPE_CHECKING
from uuid import NAMESPACE_URL, UUID, uuid5

from src.courses.models import Course, Lesson
from src.courses.schemas import CourseResponse, LessonResponse, ModuleResponse


# Local, zero-dependency module id: stable UUIDv5 from name
# NOTE: Keep this intentionally simple; we only need stability across responses.
def compute_module_id(course_id: UUID, module_name: str | None) -> UUID:
    """Return a deterministic UUID for a course module label.

    Parameters
    ----------
    course_id : UUID
        Course identifier used as part of the deterministic key.
    module_name : str | None
        Human label for the module; when ``None``, the label defaults to ``"default"``.

    Returns
    -------
    UUID
        A stable UUIDv5 derived from ``course_id`` and ``module_name``.
    """
    module_key = module_name or "default"
    return uuid5(NAMESPACE_URL, f"course-module:{course_id}:{module_key}")


if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CourseResponseBuilder:
    """Service for building course response objects."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def build_course_response(self, course: Course, lessons: Iterable[Lesson]) -> CourseResponse:
        """Build a course response grouping lessons into virtual modules."""
        lesson_responses = [self._build_lesson_response(lesson) for lesson in lessons]
        modules = self._group_lessons_into_modules(course.id, lesson_responses)

        setup_commands: list[str] = []
        if course.setup_commands:
            with contextlib.suppress(Exception):
                setup_commands = json.loads(course.setup_commands)

        return CourseResponse(
            id=course.id,
            title=course.title,
            description=course.description,
            tags=course.tags or "[]",
            setup_commands=setup_commands,
            archived=course.archived,
            user_id=course.user_id,
            adaptive_enabled=course.adaptive_enabled,
            modules=modules,
            created_at=course.created_at,
            updated_at=course.updated_at,
        )

    @staticmethod
    def build_course_list(courses: Iterable[Course]) -> list[CourseResponse]:
        """Build a list of course responses from course models."""
        responses: list[CourseResponse] = []
        for course in courses:
            setup_commands: list[str] = []
            if course.setup_commands:
                with contextlib.suppress(Exception):
                    setup_commands = json.loads(course.setup_commands)

            responses.append(
                CourseResponse(
                    id=course.id,
                    title=course.title,
                    description=course.description,
                    tags=course.tags or "[]",
                    setup_commands=setup_commands,
                    archived=course.archived,
                    user_id=course.user_id,
                    adaptive_enabled=course.adaptive_enabled,
                    modules=[],
                    created_at=course.created_at,
                    updated_at=course.updated_at,
                )
            )
        return responses

    def _group_lessons_into_modules(self, course_id: UUID, lessons: list[LessonResponse]) -> list[ModuleResponse]:
        """Group lessons by module name and order them appropriately."""
        grouped: dict[tuple[str | None, int | None], list[LessonResponse]] = defaultdict(list)
        for lesson in lessons:
            key = (lesson.module_name, lesson.module_order)
            grouped[key].append(lesson)

        modules: list[ModuleResponse] = []
        sorted_groups = sorted(
            grouped.items(),
            key=lambda kv: (
                kv[0][1] is None,
                kv[0][1] if kv[0][1] is not None else 1_000_000,
                (kv[0][0] or "").lower(),
            ),
        )

        for index, ((module_name, module_order), module_lessons) in enumerate(sorted_groups):
            module_lessons.sort(
                key=lambda lesson_response: (lesson_response.order, lesson_response.title or "")
            )
            module_id = compute_module_id(course_id, module_name)
            title = module_name or "Lessons"
            order_value = module_order if module_order is not None else index

            modules.append(
                ModuleResponse(
                    id=module_id,
                    course_id=course_id,
                    title=title,
                    module_name=module_name,
                    order=order_value,
                    lessons=module_lessons,
                )
            )

        return modules

    def _build_lesson_response(self, lesson: Lesson) -> LessonResponse:
        """Build a lesson response from a lesson model."""
        module_id = compute_module_id(lesson.course_id, lesson.module_name)
        return LessonResponse(
            id=lesson.id,
            course_id=lesson.course_id,
            module_id=module_id,
            title=lesson.title,
            description=lesson.description,
            content=lesson.content,
            html_cache=None,
            citations=[],
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
            module_name=lesson.module_name,
            module_order=lesson.module_order,
            order=lesson.order,
        )
