"""Context packet assembly for assistant turns."""

import uuid
from datetime import UTC, datetime

from src.learning_capabilities.schemas import (
    BuildContextBundleCapabilityInput,
    BuildContextBundleCapabilityOutput,
    CourseMatch,
    GetCourseFrontierCapabilityInput,
    GetCourseOutlineStateCapabilityInput,
    GetCourseStateCapabilityInput,
    GetLessonStateCapabilityInput,
    ListRelevantCoursesCapabilityInput,
)
from src.learning_capabilities.services.query_service import LearningCapabilityQueryService


class LearningContextPacketService:
    """Build compact capability-backed context packets."""

    def __init__(self, query_service: LearningCapabilityQueryService) -> None:
        self._query_service = query_service

    async def build_context_bundle(
        self,
        *,
        user_id: uuid.UUID,
        payload: BuildContextBundleCapabilityInput,
    ) -> BuildContextBundleCapabilityOutput:
        """Build a compact context packet for one assistant request."""
        selected_quote = payload.selected_quote or _extract_leading_blockquote(payload.latest_user_text)
        query_text = (selected_quote or payload.latest_user_text or "").strip()
        context_id = payload.context_id
        context_type = payload.context_type
        relevant_courses = []
        if query_text:
            include_archived = context_type == "course"
            relevant_courses = (
                await self._query_service.list_relevant_courses(
                    user_id=user_id,
                    payload=ListRelevantCoursesCapabilityInput(query=query_text, limit=6),
                    include_archived=include_archived,
                )
            ).items

        course_state = None
        course_outline = None
        lesson_state = None
        frontier_state = None
        course_catalog = None
        adaptive_catalog = None

        if context_type is None:
            course_catalog = await self._query_service.list_course_catalog(user_id=user_id)
            adaptive_catalog = await self._query_service.list_adaptive_catalog(user_id=user_id)

        if context_type == "course" and context_id is not None:
            course_state = (
                await self._query_service.get_course_state(
                    user_id=user_id,
                    payload=GetCourseStateCapabilityInput(course_id=context_id),
                )
            ).state
            course_outline = (
                await self._query_service.get_course_outline_state(
                    user_id=user_id,
                    payload=GetCourseOutlineStateCapabilityInput(course_id=context_id),
                )
            ).state
            frontier_state = (
                await self._query_service.get_course_frontier(
                    user_id=user_id,
                    payload=GetCourseFrontierCapabilityInput(course_id=context_id),
                )
            ).state

            lesson_id = _parse_lesson_id(payload.context_meta.get("lesson_id"))
            if lesson_id is not None:
                lesson_state = (
                    await self._query_service.get_lesson_state(
                        user_id=user_id,
                        payload=GetLessonStateCapabilityInput(
                            course_id=context_id,
                            lesson_id=lesson_id,
                            generate=False,
                        ),
                    )
                ).state

            if not relevant_courses:
                relevant_courses = [
                    CourseMatch(
                        id=course_state.course_id,
                        title=course_state.title,
                        description=course_state.description,
                        adaptive_enabled=course_state.adaptive_enabled,
                        completion_percentage=course_state.completion_percentage,
                    )
                ]

        return BuildContextBundleCapabilityOutput(
            app_surface=context_type,
            context_type=context_type,
            context_id=context_id,
            selected_quote=selected_quote or None,
            relevant_courses=relevant_courses,
            course_catalog=course_catalog,
            adaptive_catalog=adaptive_catalog,
            course_state=course_state,
            course_outline=course_outline,
            lesson_state=lesson_state,
            frontier_state=frontier_state,
            generated_at=datetime.now(UTC),
        )


def _extract_leading_blockquote(text: str) -> str:
    lines = text.splitlines()
    extracted: list[str] = []
    for line in lines:
        index = 0
        while index < len(line) and line[index] == " ":
            index += 1
        if index >= len(line) or line[index] != ">":
            break
        index += 1
        if index < len(line) and line[index] == " ":
            index += 1
        extracted.append(line[index:])
    return "\n".join(extracted).strip()


def _parse_lesson_id(raw: object) -> uuid.UUID | None:
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str):
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None
