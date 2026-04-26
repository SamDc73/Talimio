"""Read-side learning capability service."""

import logging
import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.assistant.models import AssistantActiveProbe
from src.ai.rag.embeddings import VectorRAG
from src.ai.rag.exceptions import RagUnavailableError
from src.ai.rag.service import RAGService
from src.config.settings import get_settings
from src.courses.facade import CoursesFacade
from src.courses.models import (
    Concept,
    ConceptPrerequisite,
    ConceptSimilarity,
    Course,
    CourseConcept,
    CourseDocument,
    Lesson,
    LessonVersion,
    LessonVersionWindow,
    ProbeEvent,
    UserConceptState,
)
from src.courses.services.course_progress_service import CourseProgressService
from src.courses.services.course_query_service import CourseQueryService
from src.courses.services.lesson_service import LessonService
from src.learning_capabilities.schemas import (
    ActiveChatProbe,
    ActiveProbeSuggestion,
    AdaptiveCatalogEntry,
    ConceptFocus,
    ConceptMatch,
    ConceptMatchSource,
    ConceptRelationSignal,
    CourseCatalogEntry,
    CourseFrontierState,
    CourseMatch,
    CourseMode,
    CourseOutlineLessonState,
    CourseOutlineState,
    CourseSourceExcerpt,
    CourseState,
    FocusedConceptState,
    FrontierConceptState,
    GetConceptTutorContextCapabilityInput,
    GetConceptTutorContextCapabilityOutput,
    GetCourseFrontierCapabilityInput,
    GetCourseFrontierCapabilityOutput,
    GetCourseOutlineStateCapabilityInput,
    GetCourseOutlineStateCapabilityOutput,
    GetCourseStateCapabilityInput,
    GetCourseStateCapabilityOutput,
    GetLessonStateCapabilityInput,
    GetLessonStateCapabilityOutput,
    GetLessonWindowsCapabilityInput,
    GetLessonWindowsCapabilityOutput,
    LearnerProfileSignals,
    LessonFocus,
    LessonMatch,
    LessonState,
    LessonWindowState,
    ListRelevantCoursesCapabilityInput,
    ListRelevantCoursesCapabilityOutput,
    RecentProbeSignal,
    SearchConceptsCapabilityInput,
    SearchConceptsCapabilityOutput,
    SearchCourseSourcesCapabilityInput,
    SearchCourseSourcesCapabilityOutput,
    SearchLessonsCapabilityInput,
    SearchLessonsCapabilityOutput,
    SourceFocus,
    TutorCandidateCause,
    TutorDeterministicSignals,
    TutorEvidenceSignals,
)


logger = logging.getLogger(__name__)

_AUTO_CONCEPT_CANDIDATE_LIMIT = 3
_AUTO_SOURCE_FOCUS_LIMIT = 2
_CONCEPT_SEARCH_EMBEDDING_MIN_CHARS = 8
_MIN_EMBEDDING_CONCEPT_SIMILARITY = 0.2
_FOCUS_WINDOW_PREVIEW_CHARS = 700
_SOURCE_FOCUS_QUERY_MIN_CHARS = 12
_SOURCE_EXCERPT_CHARS = 900
_RELATED_CONCEPT_LIMIT = 3
_RECENT_PROBE_LIMIT = 5
_STALE_EVIDENCE_DAYS = 30


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

    async def search_concepts(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchConceptsCapabilityInput,
    ) -> SearchConceptsCapabilityOutput:
        """Search adaptive course concepts with course ownership enforced first."""
        query_service = CourseQueryService(self._session)
        course = await query_service.get_course(payload.course_id, user_id)
        course_mode = _course_mode(course)
        if not course.adaptive_enabled:
            return SearchConceptsCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                items=[],
                reason="standard_course_has_no_concept_graph",
            )

        items = await self._match_course_concepts(
            user_id=user_id,
            course_id=course.id,
            query_text=payload.query,
            limit=payload.limit,
            include_state=payload.include_state,
        )
        return SearchConceptsCapabilityOutput(course_id=course.id, course_mode=course_mode, items=items)

    async def search_course_sources(
        self,
        *,
        user_id: uuid.UUID,
        payload: SearchCourseSourcesCapabilityInput,
    ) -> SearchCourseSourcesCapabilityOutput:
        """Search uploaded course sources with course ownership enforced first."""
        query_service = CourseQueryService(self._session)
        course = await query_service.get_course(payload.course_id, user_id)
        if "course_document" not in payload.source_types:
            return SearchCourseSourcesCapabilityOutput(course_id=course.id, items=[])
        query_text = payload.query.strip()
        if not query_text:
            return SearchCourseSourcesCapabilityOutput(course_id=course.id, items=[])

        results = await RAGService().search_documents(
            self._session,
            user_id,
            course.id,
            query_text,
            payload.limit,
        )
        items = [_build_source_excerpt(course_id=course.id, result=result) for result in results]
        return SearchCourseSourcesCapabilityOutput(course_id=course.id, items=items)

    async def get_source_focus(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        query_text: str,
    ) -> SourceFocus | None:
        """Return a tiny source focus when embedded course documents can ground the turn."""
        compact_query = query_text.strip()
        if len(compact_query) < _SOURCE_FOCUS_QUERY_MIN_CHARS:
            return None
        if not await self._has_embedded_course_documents(course_id=course_id):
            return None

        try:
            results = await self.search_course_sources(
                user_id=user_id,
                payload=SearchCourseSourcesCapabilityInput(
                    course_id=course_id,
                    query=compact_query,
                    limit=_AUTO_SOURCE_FOCUS_LIMIT,
                ),
            )
        except RagUnavailableError:
            logger.warning(
                "learning_capability.source_focus.unavailable",
                extra={"user_id": str(user_id), "course_id": str(course_id)},
                exc_info=True,
            )
            return None

        if not results.items:
            return None
        return SourceFocus(course_id=course_id, items=results.items[:_AUTO_SOURCE_FOCUS_LIMIT])

    async def get_mode_aware_focus(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID | None,
        latest_user_text: str,
    ) -> tuple[CourseMode, LearnerProfileSignals | None, ConceptFocus | None, LessonFocus | None]:
        """Return compact mode-aware focus for one owned course."""
        query_service = CourseQueryService(self._session)
        course = await query_service.get_course(course_id, user_id)
        course_mode = _course_mode(course)

        if not course.adaptive_enabled:
            lesson_focus = None
            if lesson_id is not None:
                lesson_focus = await self._get_lesson_focus(course_id=course.id, lesson_id=lesson_id)
            return course_mode, None, None, lesson_focus

        current_lesson_concept = None
        current_state = None
        if lesson_id is not None:
            current_lesson_concept, current_state = await self._get_current_lesson_concept(
                user_id=user_id,
                course_id=course.id,
                lesson_id=lesson_id,
            )

        semantic_candidates = await self._match_course_concepts(
            user_id=user_id,
            course_id=course.id,
            query_text=latest_user_text,
            limit=_AUTO_CONCEPT_CANDIDATE_LIMIT,
            include_state=True,
        )
        concept_focus = None
        if current_lesson_concept is not None or semantic_candidates:
            concept_focus = ConceptFocus(
                current_lesson_concept=current_lesson_concept,
                semantic_candidates=semantic_candidates,
            )

        learner_profile = _learner_profile_from_state(current_state)
        if learner_profile is None and semantic_candidates:
            candidate_state = await self._get_user_concept_state(
                user_id=user_id,
                concept_id=semantic_candidates[0].concept_id,
            )
            learner_profile = _learner_profile_from_state(candidate_state)

        return course_mode, learner_profile, concept_focus, None

    async def get_active_probe_suggestion(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        course_mode: CourseMode | None,
        concept_focus: ConceptFocus | None,
        latest_user_text: str,
    ) -> ActiveProbeSuggestion | None:
        """Return a conservative signal that a chat probe may be useful."""
        if course_mode != "adaptive" or concept_focus is None:
            return None

        focused_concept = concept_focus.current_lesson_concept
        if focused_concept is None and concept_focus.semantic_candidates:
            focused_concept = concept_focus.semantic_candidates[0]
        if focused_concept is None:
            return None

        learner_asked_check = _learner_asked_check(latest_user_text)
        learner_expressed_uncertainty = _learner_expressed_uncertainty(latest_user_text)
        learner_shared_reasoning = _learner_shared_reasoning(latest_user_text)
        repeated_recent_misses = await self._has_repeated_recent_misses(
            user_id=user_id,
            concept_id=focused_concept.concept_id,
        )
        if not any(
            [
                learner_asked_check,
                learner_expressed_uncertainty,
                learner_shared_reasoning,
                repeated_recent_misses,
            ]
        ):
            return None

        return ActiveProbeSuggestion(
            course_id=course_id,
            concept_id=focused_concept.concept_id,
            lesson_id=focused_concept.lesson_id,
            learner_asked_check=learner_asked_check,
            learner_expressed_uncertainty=learner_expressed_uncertainty,
            learner_shared_reasoning=learner_shared_reasoning,
            repeated_recent_misses=repeated_recent_misses,
        )

    async def get_active_chat_probe(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        thread_id: uuid.UUID | None,
        lesson_id: uuid.UUID | None = None,
    ) -> ActiveChatProbe | None:
        """Return the learner-visible active probe for the current assistant thread."""
        if thread_id is None or lesson_id is None:
            return None
        filters = [
            AssistantActiveProbe.user_id == user_id,
            AssistantActiveProbe.conversation_id == thread_id,
            AssistantActiveProbe.course_id == course_id,
            AssistantActiveProbe.status == "active",
            AssistantActiveProbe.lesson_id == lesson_id,
        ]
        active_probe = await self._session.scalar(
            select(AssistantActiveProbe)
            .where(*filters)
            .order_by(AssistantActiveProbe.created_at.desc())
            .limit(1)
        )
        if active_probe is None:
            return None
        return ActiveChatProbe(
            active_probe_id=active_probe.id,
            course_id=active_probe.course_id,
            concept_id=active_probe.concept_id,
            lesson_id=active_probe.lesson_id,
            question=active_probe.question,
            answer_kind=active_probe.answer_kind,
            hints=list(active_probe.hints),
        )

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

    async def get_lesson_windows(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetLessonWindowsCapabilityInput,
    ) -> GetLessonWindowsCapabilityOutput:
        """Return current-version lesson windows without loading full lesson content."""
        query_service = CourseQueryService(self._session)
        course = await query_service.get_course(payload.course_id, user_id)
        lesson = await self._session.scalar(
            select(Lesson).where(
                Lesson.id == payload.lesson_id,
                Lesson.course_id == course.id,
            )
        )
        if lesson is None:
            return GetLessonWindowsCapabilityOutput(course_id=course.id, lesson_id=payload.lesson_id)
        if lesson.current_version_id is None:
            return GetLessonWindowsCapabilityOutput(course_id=course.id, lesson_id=lesson.id)
        version_id = await self._session.scalar(
            select(LessonVersion.id).where(
                LessonVersion.id == lesson.current_version_id,
                LessonVersion.lesson_id == lesson.id,
            )
        )
        if version_id is None:
            return GetLessonWindowsCapabilityOutput(course_id=course.id, lesson_id=lesson.id)

        stmt = (
            select(LessonVersionWindow)
            .where(LessonVersionWindow.lesson_version_id == version_id)
            .order_by(LessonVersionWindow.window_index.asc())
            .limit(payload.limit)
        )
        if payload.window_index is not None:
            stmt = stmt.where(LessonVersionWindow.window_index >= payload.window_index)

        windows = (await self._session.execute(stmt)).scalars().all()
        return GetLessonWindowsCapabilityOutput(
            course_id=course.id,
            lesson_id=lesson.id,
            version_id=version_id,
            items=[
                LessonWindowState(
                    window_id=window.id,
                    lesson_id=lesson.id,
                    version_id=version_id,
                    window_index=window.window_index,
                    title=window.title,
                    content=window.content,
                    estimated_minutes=window.estimated_minutes,
                )
                for window in windows
            ],
        )

    async def get_concept_tutor_context(
        self,
        *,
        user_id: uuid.UUID,
        payload: GetConceptTutorContextCapabilityInput,
    ) -> GetConceptTutorContextCapabilityOutput:
        """Return deterministic adaptive tutor evidence for one owned course concept."""
        query_service = CourseQueryService(self._session)
        course = await query_service.get_course(payload.course_id, user_id)
        course_mode = _course_mode(course)
        if course_mode == "standard":
            return GetConceptTutorContextCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason="standard_course_has_no_concept_graph",
            )

        row = (
            await self._session.execute(
                select(Concept, Lesson, UserConceptState)
                .join(CourseConcept, and_(CourseConcept.concept_id == Concept.id, CourseConcept.course_id == course.id))
                .outerjoin(Lesson, and_(Lesson.course_id == course.id, Lesson.concept_id == Concept.id))
                .outerjoin(
                    UserConceptState,
                    and_(UserConceptState.user_id == user_id, UserConceptState.concept_id == Concept.id),
                )
                .where(Concept.id == payload.concept_id)
                .limit(1)
            )
        ).first()
        if row is None:
            return GetConceptTutorContextCapabilityOutput(
                course_id=course.id,
                course_mode=course_mode,
                concept_id=payload.concept_id,
                reason="concept_not_assigned_to_course",
            )

        concept, lesson, state = row
        recent_probes = await self._get_recent_probe_signals(
            user_id=user_id,
            concept_id=concept.id,
            include_recent_probes=payload.include_recent_probes,
        )
        prerequisite_gaps = await self._get_prerequisite_gap_signals(
            user_id=user_id,
            course_id=course.id,
            concept_id=concept.id,
        )
        semantic_confusors = await self._get_semantic_confusor_signals(course_id=course.id, concept_id=concept.id)
        downstream_blocked = await self._get_downstream_blocked_signals(
            user_id=user_id,
            course_id=course.id,
            concept_id=concept.id,
        )
        content_source_count = await self._count_verified_lesson_content_sources(
            lesson=lesson,
            include_lesson_summary=payload.include_lesson_summary,
        )
        evidence = _build_tutor_evidence(state=state, recent_probes=recent_probes)
        due = _is_due(state.next_review_at) if state is not None else False
        candidate_causes = _build_tutor_candidate_causes(
            concept_id=concept.id,
            lesson_id=lesson.id if lesson is not None else None,
            recent_probes=recent_probes,
            prerequisite_gaps=prerequisite_gaps,
            semantic_confusors=semantic_confusors,
        )

        return GetConceptTutorContextCapabilityOutput(
            course_id=course.id,
            course_mode=course_mode,
            concept_id=concept.id,
            concept_name=concept.name,
            description=concept.description,
            difficulty=float(concept.difficulty) if concept.difficulty is not None else None,
            lesson_id=lesson.id if lesson is not None else None,
            lesson_title=lesson.title if lesson is not None else None,
            mastery=float(state.s_mastery) if state is not None else None,
            exposures=state.exposures if state is not None else 0,
            next_review_at=state.next_review_at if state is not None else None,
            due=due,
            learner_profile=_learner_profile_from_state(state),
            recent_probes=recent_probes,
            prerequisite_gaps=prerequisite_gaps,
            semantic_confusors=semantic_confusors,
            downstream_blocked=downstream_blocked,
            has_verified_content=content_source_count > 0,
            content_source_count=content_source_count,
            evidence=evidence,
            candidate_causes=candidate_causes,
            deterministic_signals=TutorDeterministicSignals(
                has_prerequisite_gap=bool(prerequisite_gaps),
                has_recent_miss=any(not probe.correct for probe in recent_probes),
                due=due,
                has_semantic_confusor=bool(semantic_confusors),
                exposures=state.exposures if state is not None else 0,
                recent_probe_count=evidence.recent_probe_count,
                recent_correct_count=evidence.recent_correct_count,
                mastery_evidence_count=evidence.mastery_evidence_count,
            ),
        )

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

    async def _has_embedded_course_documents(self, *, course_id: uuid.UUID) -> bool:
        document_id = await self._session.scalar(
            select(CourseDocument.id)
            .where(
                CourseDocument.course_id == course_id,
                CourseDocument.status == "embedded",
            )
            .limit(1)
        )
        return document_id is not None

    async def _get_lesson_focus(self, *, course_id: uuid.UUID, lesson_id: uuid.UUID) -> LessonFocus | None:
        lesson = await self._session.scalar(
            select(Lesson).where(
                Lesson.course_id == course_id,
                Lesson.id == lesson_id,
            )
        )
        if lesson is None:
            return None

        window_preview = None
        if lesson.current_version_id is not None:
            window = await self._session.scalar(
                select(LessonVersionWindow)
                .where(LessonVersionWindow.lesson_version_id == lesson.current_version_id)
                .order_by(LessonVersionWindow.window_index.asc())
                .limit(1)
            )
            if window is not None:
                window_preview = _compact_text(window.content, _FOCUS_WINDOW_PREVIEW_CHARS)

        return LessonFocus(
            lesson_id=lesson.id,
            title=lesson.title,
            description=lesson.description,
            has_content=bool((lesson.content or "").strip() or window_preview),
            window_preview=window_preview,
        )

    async def _get_current_lesson_concept(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> tuple[FocusedConceptState | None, UserConceptState | None]:
        row = (
            await self._session.execute(
                select(Concept, Lesson, UserConceptState)
                .select_from(Lesson)
                .join(Concept, Concept.id == Lesson.concept_id)
                .outerjoin(
                    UserConceptState,
                    and_(
                        UserConceptState.user_id == user_id,
                        UserConceptState.concept_id == Concept.id,
                    ),
                )
                .where(
                    Lesson.course_id == course_id,
                    Lesson.id == lesson_id,
                    Lesson.concept_id.is_not(None),
                )
            )
        ).first()
        if row is None:
            return None, None

        concept, lesson, state = row
        item = FocusedConceptState(
            concept_id=concept.id,
            name=concept.name,
            description=concept.description,
            lesson_id=lesson.id,
            lesson_title=lesson.title,
            mastery=float(state.s_mastery) if state is not None else None,
            exposures=int(state.exposures) if state is not None else 0,
            next_review_at=state.next_review_at if state is not None else None,
            due=_is_due(state.next_review_at if state is not None else None),
        )
        await self._attach_related_concept_signals(user_id=user_id, course_id=course_id, items=[item])
        return item, state

    async def _get_user_concept_state(
        self,
        *,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> UserConceptState | None:
        return await self._session.scalar(
            select(UserConceptState).where(
                UserConceptState.user_id == user_id,
                UserConceptState.concept_id == concept_id,
            )
        )

    async def _match_course_concepts(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        query_text: str,
        limit: int,
        include_state: bool,
    ) -> list[ConceptMatch]:
        query_text = query_text.strip()
        if not query_text:
            return []

        matches: list[ConceptMatch] = []
        if len(query_text) >= _CONCEPT_SEARCH_EMBEDDING_MIN_CHARS:
            matches = await self._match_course_concepts_by_embedding(
                user_id=user_id,
                course_id=course_id,
                query_text=query_text,
                limit=limit,
                include_state=include_state,
            )

        if not matches:
            matches = await self._match_course_concepts_by_lexical(
                user_id=user_id,
                course_id=course_id,
                query_text=query_text,
                limit=limit,
                include_state=include_state,
            )

        _apply_score_gaps(matches)
        await self._attach_related_concept_signals(
            user_id=user_id,
            course_id=course_id,
            items=matches,
            include_state=include_state,
        )
        return matches

    async def _match_course_concepts_by_embedding(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        query_text: str,
        limit: int,
        include_state: bool,
    ) -> list[ConceptMatch]:
        try:
            query_embedding = await VectorRAG().generate_embedding(query_text)
        except (RuntimeError, TimeoutError, TypeError, ValueError):
            return []

        rows = (
            await self._session.execute(
                text(
                    """
                    SELECT
                        c.id AS concept_id,
                        c.name AS name,
                        c.description AS description,
                        l.id AS lesson_id,
                        l.title AS lesson_title,
                        ucs.s_mastery AS mastery,
                        ucs.exposures AS exposures,
                        ucs.next_review_at AS next_review_at,
                        GREATEST(
                            0.0::double precision,
                            1.0::double precision - (c.embedding <=> CAST(:query_embedding AS vector))
                        ) AS similarity
                    FROM course_concepts cc
                    JOIN concepts c ON c.id = cc.concept_id
                    LEFT JOIN lessons l ON l.course_id = cc.course_id AND l.concept_id = c.id
                    LEFT JOIN user_concept_state ucs ON ucs.user_id = :user_id AND ucs.concept_id = c.id
                    WHERE cc.course_id = :course_id
                      AND c.embedding IS NOT NULL
                    ORDER BY c.embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :limit
                    """
                ),
                {
                    "course_id": str(course_id),
                    "user_id": str(user_id),
                    "query_embedding": _format_vector(query_embedding),
                    "limit": limit,
                },
            )
        ).all()

        matches: list[ConceptMatch] = []
        for row in rows:
            similarity = float(row.similarity or 0.0)
            if similarity < _MIN_EMBEDDING_CONCEPT_SIMILARITY:
                continue
            matches.append(
                _build_concept_match(
                    concept_id=row.concept_id,
                    name=row.name,
                    description=row.description,
                    lesson_id=row.lesson_id,
                    lesson_title=row.lesson_title,
                    mastery=row.mastery,
                    exposures=row.exposures,
                    next_review_at=row.next_review_at,
                    match_score=similarity,
                    match_source="embedding",
                    candidate_rank=len(matches) + 1,
                    similarity=similarity,
                    include_state=include_state,
                )
            )
        return matches

    async def _match_course_concepts_by_lexical(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        query_text: str,
        limit: int,
        include_state: bool,
    ) -> list[ConceptMatch]:
        pattern = f"%{query_text}%"
        score_expr = case(
            (Concept.name.ilike(query_text), 1.0),
            (Concept.name.ilike(pattern), 0.85),
            (Concept.description.ilike(pattern), 0.65),
            else_=0.0,
        )

        rows = (
            await self._session.execute(
                select(Concept, Lesson, UserConceptState, score_expr.label("match_score"))
                .select_from(CourseConcept)
                .join(Concept, Concept.id == CourseConcept.concept_id)
                .outerjoin(Lesson, and_(Lesson.course_id == CourseConcept.course_id, Lesson.concept_id == Concept.id))
                .outerjoin(
                    UserConceptState,
                    and_(
                        UserConceptState.user_id == user_id,
                        UserConceptState.concept_id == Concept.id,
                    ),
                )
                .where(CourseConcept.course_id == course_id)
                .where(or_(Concept.name.ilike(pattern), Concept.description.ilike(pattern)))
                .order_by(score_expr.desc(), Concept.name.asc())
                .limit(limit)
            )
        ).all()

        matches: list[ConceptMatch] = []
        for index, (concept, lesson, state, match_score) in enumerate(rows, start=1):
            score = float(match_score or 0.0)
            matches.append(
                _build_concept_match(
                    concept_id=concept.id,
                    name=concept.name,
                    description=concept.description,
                    lesson_id=lesson.id if lesson is not None else None,
                    lesson_title=lesson.title if lesson is not None else None,
                    mastery=state.s_mastery if state is not None else None,
                    exposures=state.exposures if state is not None else None,
                    next_review_at=state.next_review_at if state is not None else None,
                    match_score=score,
                    match_source="lexical",
                    candidate_rank=index,
                    similarity=None,
                    include_state=include_state,
                )
            )

        return matches

    async def _attach_related_concept_signals(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        items: Sequence[FocusedConceptState],
        include_state: bool = True,
    ) -> None:
        concept_ids = [item.concept_id for item in items]
        if not concept_ids:
            return

        item_by_id = {item.concept_id: item for item in items}
        await self._attach_confusors(course_id=course_id, concept_ids=concept_ids, item_by_id=item_by_id)
        if not include_state:
            return
        await self._attach_prerequisite_gaps(
            user_id=user_id,
            course_id=course_id,
            concept_ids=concept_ids,
            item_by_id=item_by_id,
        )

    async def _attach_confusors(
        self,
        *,
        course_id: uuid.UUID,
        concept_ids: Sequence[uuid.UUID],
        item_by_id: dict[uuid.UUID, FocusedConceptState],
    ) -> None:
        rows = (
            await self._session.execute(
                select(ConceptSimilarity, Concept)
                .join(
                    Concept,
                    or_(
                        and_(ConceptSimilarity.concept_a_id.in_(concept_ids), Concept.id == ConceptSimilarity.concept_b_id),
                        and_(ConceptSimilarity.concept_b_id.in_(concept_ids), Concept.id == ConceptSimilarity.concept_a_id),
                    ),
                )
                .join(CourseConcept, and_(CourseConcept.course_id == course_id, CourseConcept.concept_id == Concept.id))
                .where(
                    or_(
                        ConceptSimilarity.concept_a_id.in_(concept_ids),
                        ConceptSimilarity.concept_b_id.in_(concept_ids),
                    )
                )
                .order_by(ConceptSimilarity.similarity.desc())
            )
        ).all()

        for similarity, related_concept in rows:
            if related_concept.id == similarity.concept_b_id:
                candidate_id = similarity.concept_a_id
            else:
                candidate_id = similarity.concept_b_id
            item = item_by_id.get(candidate_id)
            if item is None or len(item.confusors) >= _RELATED_CONCEPT_LIMIT:
                continue
            item.confusors.append(
                ConceptRelationSignal(
                    concept_id=related_concept.id,
                    name=related_concept.name,
                    similarity=float(similarity.similarity),
                )
            )

    async def _attach_prerequisite_gaps(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_ids: Sequence[uuid.UUID],
        item_by_id: dict[uuid.UUID, FocusedConceptState],
    ) -> None:
        threshold = float(get_settings().ADAPTIVE_UNLOCK_MASTERY_THRESHOLD)
        rows = (
            await self._session.execute(
                select(ConceptPrerequisite.concept_id, Concept, UserConceptState)
                .select_from(ConceptPrerequisite)
                .join(Concept, Concept.id == ConceptPrerequisite.prereq_id)
                .join(CourseConcept, and_(CourseConcept.course_id == course_id, CourseConcept.concept_id == Concept.id))
                .outerjoin(
                    UserConceptState,
                    and_(
                        UserConceptState.user_id == user_id,
                        UserConceptState.concept_id == Concept.id,
                    ),
                )
                .where(ConceptPrerequisite.concept_id.in_(concept_ids))
                .order_by(Concept.name.asc())
            )
        ).all()

        for concept_id, prerequisite, state in rows:
            mastery = float(state.s_mastery) if state is not None else None
            if mastery is not None and mastery >= threshold:
                continue
            item = item_by_id.get(concept_id)
            if item is None or len(item.prerequisite_gaps) >= _RELATED_CONCEPT_LIMIT:
                continue
            item.prerequisite_gaps.append(
                ConceptRelationSignal(
                    concept_id=prerequisite.id,
                    name=prerequisite.name,
                    mastery=mastery,
                )
            )

    async def _get_recent_probe_signals(
        self,
        *,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
        include_recent_probes: bool,
    ) -> list[RecentProbeSignal]:
        if not include_recent_probes:
            return []
        probes = (
            await self._session.execute(
                select(ProbeEvent)
                .where(ProbeEvent.user_id == user_id, ProbeEvent.concept_id == concept_id)
                .order_by(ProbeEvent.ts.desc())
                .limit(_RECENT_PROBE_LIMIT)
            )
        ).scalars()
        return [
            RecentProbeSignal(
                probe_id=probe.id,
                concept_id=probe.concept_id,
                correct=probe.correct,
                occurred_at=probe.ts,
            )
            for probe in probes
        ]

    async def _has_repeated_recent_misses(self, *, user_id: uuid.UUID, concept_id: uuid.UUID) -> bool:
        outcomes = (
            await self._session.execute(
                select(ProbeEvent.correct)
                .where(ProbeEvent.user_id == user_id, ProbeEvent.concept_id == concept_id)
                .order_by(ProbeEvent.ts.desc())
                .limit(3)
            )
        ).scalars()
        return sum(1 for correct in outcomes if not correct) >= 2

    async def _get_prerequisite_gap_signals(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> list[ConceptRelationSignal]:
        item = FocusedConceptState(concept_id=concept_id, name="unused")
        await self._attach_prerequisite_gaps(
            user_id=user_id,
            course_id=course_id,
            concept_ids=[concept_id],
            item_by_id={concept_id: item},
        )
        return item.prerequisite_gaps

    async def _get_semantic_confusor_signals(
        self,
        *,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> list[ConceptRelationSignal]:
        item = FocusedConceptState(concept_id=concept_id, name="unused")
        await self._attach_confusors(
            course_id=course_id,
            concept_ids=[concept_id],
            item_by_id={concept_id: item},
        )
        return item.confusors

    async def _get_downstream_blocked_signals(
        self,
        *,
        user_id: uuid.UUID,
        course_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> list[ConceptRelationSignal]:
        threshold = float(get_settings().ADAPTIVE_UNLOCK_MASTERY_THRESHOLD)
        rows = (
            await self._session.execute(
                select(Concept, UserConceptState)
                .select_from(ConceptPrerequisite)
                .join(Concept, Concept.id == ConceptPrerequisite.concept_id)
                .join(CourseConcept, and_(CourseConcept.course_id == course_id, CourseConcept.concept_id == Concept.id))
                .outerjoin(
                    UserConceptState,
                    and_(UserConceptState.user_id == user_id, UserConceptState.concept_id == Concept.id),
                )
                .where(ConceptPrerequisite.prereq_id == concept_id)
                .order_by(Concept.name.asc())
                .limit(_RELATED_CONCEPT_LIMIT)
            )
        ).all()
        blocked: list[ConceptRelationSignal] = []
        for concept, state in rows:
            mastery = float(state.s_mastery) if state is not None else None
            if mastery is not None and mastery >= threshold:
                continue
            blocked.append(ConceptRelationSignal(concept_id=concept.id, name=concept.name, mastery=mastery))
        return blocked

    async def _count_verified_lesson_content_sources(
        self,
        *,
        lesson: Lesson | None,
        include_lesson_summary: bool,
    ) -> int:
        if lesson is None or lesson.current_version_id is None or not include_lesson_summary:
            return 0
        version = await self._session.scalar(
            select(LessonVersion).where(
                LessonVersion.id == lesson.current_version_id,
                LessonVersion.lesson_id == lesson.id,
            )
        )
        if version is None:
            return 0
        window_count = await self._session.scalar(
            select(func.count(LessonVersionWindow.id)).where(LessonVersionWindow.lesson_version_id == version.id)
        )
        if window_count:
            return int(window_count)
        return 1 if isinstance(version.content, str) and version.content.strip() else 0


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


def _course_mode(course: object) -> CourseMode:
    return "adaptive" if bool(getattr(course, "adaptive_enabled", False)) else "standard"


def _compact_text(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    compacted = " ".join(value.split())
    if not compacted:
        return None
    if len(compacted) <= limit:
        return compacted
    return f"{compacted[: max(0, limit - 3)].rstrip()}..."


def _build_source_excerpt(*, course_id: uuid.UUID, result: Any) -> CourseSourceExcerpt:
    metadata = result.metadata if isinstance(result.metadata, dict) else {}
    return CourseSourceExcerpt(
        course_id=course_id,
        title=_metadata_str(metadata, "title"),
        excerpt=_compact_text(getattr(result, "content", ""), _SOURCE_EXCERPT_CHARS) or "",
        similarity=float(getattr(result, "similarity_score", 0.0) or 0.0),
        chunk_id=str(getattr(result, "chunk_id", "")),
        document_id=_metadata_int(metadata, "document_id"),
        chunk_index=_metadata_int(metadata, "chunk_index"),
        total_chunks=_metadata_int(metadata, "total_chunks"),
    )


def _metadata_str(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _format_vector(values: Sequence[float]) -> str:
    return "[" + ",".join(str(float(value)) for value in values) + "]"


def _build_concept_match(
    *,
    concept_id: uuid.UUID | str,
    name: str,
    description: str | None,
    lesson_id: uuid.UUID | str | None,
    lesson_title: str | None,
    mastery: float | None,
    exposures: int | None,
    next_review_at: datetime | None,
    match_score: float,
    match_source: ConceptMatchSource,
    candidate_rank: int,
    similarity: float | None,
    include_state: bool,
) -> ConceptMatch:
    resolved_concept_id = _coerce_uuid(concept_id) if isinstance(concept_id, str) else concept_id
    resolved_lesson_id = _coerce_uuid(lesson_id) if isinstance(lesson_id, str) else lesson_id
    if resolved_concept_id is None:
        message = "concept_id is required"
        raise ValueError(message)

    return ConceptMatch(
        concept_id=resolved_concept_id,
        name=name,
        description=description,
        lesson_id=resolved_lesson_id,
        lesson_title=lesson_title,
        mastery=float(mastery) if mastery is not None and include_state else None,
        exposures=int(exposures or 0) if include_state else 0,
        next_review_at=next_review_at if include_state else None,
        due=_is_due(next_review_at) if include_state else False,
        similarity=similarity,
        match_score=match_score,
        match_source=match_source,
        candidate_rank=candidate_rank,
    )


def _apply_score_gaps(matches: Sequence[ConceptMatch]) -> None:
    for index, match in enumerate(matches):
        next_match = matches[index + 1] if index + 1 < len(matches) else None
        match.score_gap_to_next = None if next_match is None else max(0.0, match.match_score - next_match.match_score)


def _is_due(next_review_at: datetime | None) -> bool:
    if next_review_at is None:
        return False
    if next_review_at.tzinfo is None:
        next_review_at = next_review_at.replace(tzinfo=UTC)
    return next_review_at <= datetime.now(UTC)


def _is_stale(timestamp: datetime | None) -> bool:
    if timestamp is None:
        return False
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    age = datetime.now(UTC) - timestamp
    return age.days >= _STALE_EVIDENCE_DAYS


def _learner_asked_check(text_value: str) -> bool:
    lowered = text_value.lower()
    return any(
        phrase in lowered
        for phrase in (
            "check my understanding",
            "test my understanding",
            "quiz me",
            "practice question",
            "give me a question",
            "can you test",
        )
    )


def _learner_expressed_uncertainty(text_value: str) -> bool:
    lowered = text_value.lower()
    return any(
        phrase in lowered
        for phrase in (
            "i'm not sure",
            "i am not sure",
            "not sure",
            "confused",
            "stuck",
            "i don't get",
            "i do not get",
        )
    )


def _learner_shared_reasoning(text_value: str) -> bool:
    lowered = text_value.lower()
    return any(
        phrase in lowered
        for phrase in (
            "my reasoning",
            "i think",
            "because",
            "so i",
            "therefore",
            "does that mean",
        )
    )


def _build_tutor_evidence(
    *,
    state: UserConceptState | None,
    recent_probes: list[RecentProbeSignal],
) -> TutorEvidenceSignals:
    recent_probe_count = len(recent_probes)
    recent_correct_count = sum(1 for probe in recent_probes if probe.correct)
    exposures = state.exposures if state is not None else 0
    mastery_evidence_count = exposures + recent_probe_count
    last_probe_at = recent_probes[0].occurred_at if recent_probes else None
    state_updated_at = state.last_seen_at if state is not None else None
    latest_evidence_at = last_probe_at or state_updated_at
    if last_probe_at is not None and state_updated_at is not None:
        latest_evidence_at = max(last_probe_at, state_updated_at)
    return TutorEvidenceSignals(
        recent_probe_count=recent_probe_count,
        recent_correct_count=recent_correct_count,
        mastery_evidence_count=mastery_evidence_count,
        last_probe_at=last_probe_at,
        state_updated_at=state_updated_at,
        has_sparse_evidence=mastery_evidence_count < 2,
        has_stale_evidence=_is_stale(latest_evidence_at),
    )


def _build_tutor_candidate_causes(
    *,
    concept_id: uuid.UUID,
    lesson_id: uuid.UUID | None,
    recent_probes: list[RecentProbeSignal],
    prerequisite_gaps: list[ConceptRelationSignal],
    semantic_confusors: list[ConceptRelationSignal],
) -> list[TutorCandidateCause]:
    causes: list[TutorCandidateCause] = []
    if lesson_id is not None:
        causes.append(
            TutorCandidateCause(rank=0, kind="current_concept", concept_id=concept_id, source="course_context")
        )
    if any(not probe.correct for probe in recent_probes):
        causes.append(TutorCandidateCause(rank=0, kind="recent_miss", concept_id=concept_id, source="probe_event"))
    causes.extend(
        TutorCandidateCause(rank=0, kind="prerequisite_gap", concept_id=gap.concept_id, source="concept_graph")
        for gap in prerequisite_gaps[:1]
    )
    causes.extend(
        TutorCandidateCause(rank=0, kind="semantic_confusor", concept_id=confusor.concept_id, source="concept_similarity")
        for confusor in semantic_confusors[:1]
    )
    for index, cause in enumerate(causes, start=1):
        cause.rank = index
    return causes


def _learner_profile_from_state(state: UserConceptState | None) -> LearnerProfileSignals | None:
    if state is None or not isinstance(state.learner_profile, dict):
        return None

    profile = LearnerProfileSignals(
        success_rate=_float_or_none(state.learner_profile.get("success_rate")),
        retention_rate=_float_or_none(state.learner_profile.get("retention_rate")),
        learning_speed=_float_or_none(state.learner_profile.get("learning_speed")),
        semantic_sensitivity=_float_or_none(state.learner_profile.get("semantic_sensitivity")),
    )
    if all(value is None for value in profile.model_dump().values()):
        return None
    return profile


def _float_or_none(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
