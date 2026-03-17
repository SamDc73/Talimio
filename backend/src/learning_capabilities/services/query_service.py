"""Read-side learning capability service."""

import uuid
from collections.abc import Sequence

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.facade import CoursesFacade
from src.courses.models import Course, Lesson
from src.courses.services.course_progress_service import CourseProgressService
from src.courses.services.course_query_service import CourseQueryService
from src.courses.services.lesson_service import LessonService
from src.learning_capabilities.schemas import (
    AdaptiveCatalogEntry,
    CourseCatalogEntry,
    CourseFrontierState,
    CourseMatch,
    CourseOutlineLessonState,
    CourseOutlineState,
    CourseState,
    FrontierConceptState,
    GetCourseFrontierCapabilityInput,
    GetCourseFrontierCapabilityOutput,
    GetCourseOutlineStateCapabilityInput,
    GetCourseOutlineStateCapabilityOutput,
    GetCourseStateCapabilityInput,
    GetCourseStateCapabilityOutput,
    GetLessonStateCapabilityInput,
    GetLessonStateCapabilityOutput,
    LessonMatch,
    LessonState,
    ListRelevantCoursesCapabilityInput,
    ListRelevantCoursesCapabilityOutput,
    SearchLessonsCapabilityInput,
    SearchLessonsCapabilityOutput,
)


class LearningCapabilityQueryService:
    """Capability-backed read operations for assistant routing/context."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search_lessons(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchLessonsCapabilityInput,
    ) -> SearchLessonsCapabilityOutput:
        """Search lessons by title/description in owned courses."""
        query_text = payload.query.strip()
        pattern = f"%{query_text}%"
        stmt = (
            select(Lesson, Course)
            .join(Course, Lesson.course_id == Course.id)
            .where(Course.user_id == user_id)
            .where(
                or_(
                    Lesson.title.ilike(pattern),
                    Lesson.description.ilike(pattern),
                    Course.title.ilike(pattern),
                )
            )
            .order_by(Course.updated_at.desc(), *Lesson.course_order_by())
            .limit(payload.limit)
        )
        if payload.course_id is not None:
            stmt = stmt.where(Course.id == payload.course_id)

        rows = (await self._session.execute(stmt)).all()
        items = [
            LessonMatch(
                course_id=course.id,
                lesson_id=lesson.id,
                course_title=course.title,
                lesson_title=lesson.title,
                lesson_description=lesson.description,
                module_name=lesson.module_name,
                order=lesson.order,
            )
            for lesson, course in rows
        ]
        return SearchLessonsCapabilityOutput(items=items)

    async def list_relevant_courses(
        self,
        *,
        user_id: uuid.UUID,
        payload: ListRelevantCoursesCapabilityInput,
        include_archived: bool = True,
    ) -> ListRelevantCoursesCapabilityOutput:
        """List course matches with compact progress signals."""
        query_service = CourseQueryService(self._session)
        progress_service = CourseProgressService(self._session)
        courses, _ = await query_service.list_courses(
            user_id=user_id,
            page=1,
            per_page=payload.limit,
            search=payload.query.strip(),
            include_archived=include_archived,
        )

        items: list[CourseMatch] = []
        for course in courses:
            progress = await progress_service.get_progress(course.id, user_id)
            items.append(
                CourseMatch(
                    id=course.id,
                    title=course.title,
                    description=course.description,
                    adaptive_enabled=course.adaptive_enabled,
                    completion_percentage=float(progress.get("completion_percentage", 0.0)),
                )
            )
        return ListRelevantCoursesCapabilityOutput(items=items)

    async def get_course_state(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetCourseStateCapabilityInput,
    ) -> GetCourseStateCapabilityOutput:
        """Return compact course state with progress signals."""
        query_service = CourseQueryService(self._session)
        progress_service = CourseProgressService(self._session)
        course = await query_service.get_course(payload.course_id, user_id)
        progress = await progress_service.get_progress(payload.course_id, user_id)

        completed_lessons = _normalize_completed_lessons(progress.get("completed_lessons"))
        current_lesson_id = _coerce_uuid(progress.get("current_lesson"))
        state = CourseState(
            course_id=course.id,
            title=course.title,
            description=course.description,
            adaptive_enabled=course.adaptive_enabled,
            completion_percentage=float(progress.get("completion_percentage", 0.0)),
            total_lessons=int(progress.get("total_lessons", len(course.modules))),
            completed_lessons=completed_lessons,
            current_lesson_id=current_lesson_id,
        )
        return GetCourseStateCapabilityOutput(state=state)

    async def list_course_catalog(
        self,
        *,
        user_id: uuid.UUID,
        limit: int = 8,
    ) -> list[CourseCatalogEntry]:
        """Return a compact home-surface course catalog."""
        query_service = CourseQueryService(self._session)
        courses, _ = await query_service.list_courses(
            user_id=user_id,
            page=1,
            per_page=limit,
            search=None,
            include_archived=False,
        )
        return [
            CourseCatalogEntry(
                course_id=course.id,
                title=course.title,
                adaptive_enabled=course.adaptive_enabled,
            )
            for course in courses
        ]

    async def list_adaptive_catalog(
        self,
        *,
        user_id: uuid.UUID,
        limit: int = 8,
    ) -> list[AdaptiveCatalogEntry]:
        """Return compact adaptive course summaries for the home surface."""
        query_service = CourseQueryService(self._session)
        progress_service = CourseProgressService(self._session)
        courses, _ = await query_service.list_courses(
            user_id=user_id,
            page=1,
            per_page=limit,
            search=None,
            include_archived=False,
        )
        adaptive_courses = [course for course in courses if course.adaptive_enabled]
        if not adaptive_courses:
            return []

        course_ids = [course.id for course in adaptive_courses]
        lesson_rows = (
            await self._session.execute(
                select(Lesson.id, Lesson.title).where(Lesson.course_id.in_(course_ids))
            )
        ).all()
        lesson_title_by_id: dict[uuid.UUID, str] = {  # noqa: C416 - keeps typing precise for ty
            lesson_id: lesson_title for lesson_id, lesson_title in lesson_rows
        }

        summaries: list[AdaptiveCatalogEntry] = []
        for course in adaptive_courses:
            progress = await progress_service.get_progress(course.id, user_id)
            current_lesson_id = _coerce_uuid(progress.get("current_lesson"))
            frontier = await self.get_course_frontier(
                user_id=user_id,
                payload=GetCourseFrontierCapabilityInput(course_id=course.id),
            )
            summaries.append(
                AdaptiveCatalogEntry(
                    course_id=course.id,
                    title=course.title,
                    completion_percentage=float(progress.get("completion_percentage", 0.0)),
                    current_lesson_id=current_lesson_id,
                    current_lesson_title=lesson_title_by_id.get(current_lesson_id) if current_lesson_id is not None else None,
                    due_count=frontier.state.due_count,
                    avg_mastery=frontier.state.avg_mastery,
                )
            )
        return summaries

    async def get_course_outline_state(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetCourseOutlineStateCapabilityInput,
    ) -> GetCourseOutlineStateCapabilityOutput:
        """Return compact lesson outline state for one owned course."""
        query_service = CourseQueryService(self._session)
        progress_service = CourseProgressService(self._session)
        await query_service.get_course(payload.course_id, user_id)
        progress = await progress_service.get_progress(payload.course_id, user_id)

        completed_lessons = set(_normalize_completed_lessons(progress.get("completed_lessons")))
        current_lesson_id = _coerce_uuid(progress.get("current_lesson"))
        lesson_rows = (
            await self._session.execute(
                select(Lesson)
                .where(Lesson.course_id == payload.course_id)
                .order_by(*Lesson.course_order_by())
            )
        ).scalars().all()

        state = CourseOutlineState(
            course_id=payload.course_id,
            lessons=[
                CourseOutlineLessonState(
                    lesson_id=lesson.id,
                    title=lesson.title,
                    description=lesson.description,
                    module_name=lesson.module_name,
                    module_order=lesson.module_order,
                    order=lesson.order,
                    has_content=bool(lesson.content and lesson.content.strip()),
                    completed=lesson.id in completed_lessons,
                    is_current=lesson.id == current_lesson_id,
                )
                for lesson in lesson_rows
            ],
        )
        return GetCourseOutlineStateCapabilityOutput(state=state)

    async def get_lesson_state(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetLessonStateCapabilityInput,
    ) -> GetLessonStateCapabilityOutput:
        """Return compact lesson state for one lesson."""
        lesson_service = LessonService(self._session, user_id)
        lesson_detail = await lesson_service.get_lesson(
            payload.course_id,
            payload.lesson_id,
            force_refresh=payload.generate,
        )

        lesson_row = await self._session.scalar(
            select(Lesson).where(
                Lesson.id == payload.lesson_id,
                Lesson.course_id == payload.course_id,
            )
        )
        module_name = lesson_row.module_name if lesson_row else None
        module_order = lesson_row.module_order if lesson_row else None
        lesson_order = lesson_row.order if lesson_row else 0
        has_content = bool(lesson_detail.content and lesson_detail.content.strip())

        state = LessonState(
            course_id=lesson_detail.course_id,
            lesson_id=lesson_detail.id,
            title=lesson_detail.title,
            description=lesson_detail.description,
            content=lesson_detail.content,
            has_content=has_content,
            module_name=module_name,
            module_order=module_order,
            order=lesson_order,
        )
        return GetLessonStateCapabilityOutput(state=state)

    async def get_course_frontier(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetCourseFrontierCapabilityInput,
    ) -> GetCourseFrontierCapabilityOutput:
        """Return compact adaptive frontier state."""
        courses_facade = CoursesFacade(self._session)
        frontier = await courses_facade.get_course_concept_frontier(
            course_id=payload.course_id,
            user_id=user_id,
        )

        state = CourseFrontierState(
            due_count=frontier.due_count,
            avg_mastery=frontier.avg_mastery,
            frontier=_map_frontier_rows(frontier.frontier),
            due_for_review=_map_frontier_rows(frontier.due_for_review),
            coming_soon=_map_frontier_rows(frontier.coming_soon),
        )
        return GetCourseFrontierCapabilityOutput(state=state)


def _map_frontier_rows(rows: Sequence[object]) -> list[FrontierConceptState]:
    mapped: list[FrontierConceptState] = []
    for row in rows:
        concept_id = getattr(row, "id", None)
        name = getattr(row, "name", None)
        if not isinstance(concept_id, uuid.UUID) or not isinstance(name, str):
            continue
        mapped.append(
            FrontierConceptState(
                concept_id=concept_id,
                lesson_id=getattr(row, "lesson_id", None),
                name=name,
                mastery=getattr(row, "mastery", None),
                exposures=int(getattr(row, "exposures", 0) or 0),
                next_review_at=getattr(row, "next_review_at", None),
            )
        )
    return mapped


def _normalize_completed_lessons(raw: object) -> list[uuid.UUID]:
    if isinstance(raw, dict):
        candidates = [lesson_id for lesson_id, completed in raw.items() if completed]
    elif isinstance(raw, list):
        candidates = raw
    else:
        candidates = []
    normalized: list[uuid.UUID] = []
    for value in candidates:
        parsed = _coerce_uuid(value)
        if parsed is not None:
            normalized.append(parsed)
    return normalized


def _coerce_uuid(raw: object) -> uuid.UUID | None:
    if isinstance(raw, uuid.UUID):
        return raw
    if isinstance(raw, str):
        try:
            return uuid.UUID(raw)
        except ValueError:
            return None
    return None
