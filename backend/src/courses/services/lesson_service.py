
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession


"""Lesson service with SQL-first queries and mandatory user isolation."""


import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.exc import SQLAlchemyError

from src.ai import AGENT_ID_LESSON_WRITER
from src.ai.client import LLMClient
from src.ai.tools.wikipedia import build_wikipedia_resolver_function_tool
from src.courses.models import (
    Concept,
    Course,
    CourseConcept,
    Lesson,
    LessonFeedbackEvent,
    LessonVersion,
    ProbeEvent,
    UserConceptState,
)
from src.courses.schemas import (
    LessonDetailResponse,
    LessonNextPassResponse,
    LessonVersionHistoryResponse,
    LessonVersionSummary,
    LessonWindowResponse,
)
from src.courses.services.concept_scheduler_service import AdaptivePassRecommendation, LectorSchedulerService
from src.courses.services.lesson_version_service import LessonVersionService
from src.courses.services.lesson_window_service import LessonWindowService
from src.exceptions import ConflictError, NotFoundError, UpstreamUnavailableError, ValidationError


logger = logging.getLogger(__name__)

_LESSON_RAG_CONTEXT_FALLBACK_ERROR_TYPES = (
    ImportError,
    SQLAlchemyError,
    RuntimeError,
    TypeError,
    ValueError,
    OSError,
    ConnectionError,
    TimeoutError,
)
_LESSON_OUTLINE_FALLBACK_ERROR_TYPES = (
    SQLAlchemyError,
    RuntimeError,
    TypeError,
    ValueError,
)
_LESSON_GENERATION_HTTP_500_ERROR_TYPES = (
    SQLAlchemyError,
    OSError,
    TypeError,
    ConnectionError,
    TimeoutError,
)
_LESSON_LEARNER_STATE_FALLBACK_ERROR_TYPES = (SQLAlchemyError,)


class LessonService:
    """Lesson service with SQL-first queries and mandatory user isolation."""

    def __init__(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """Initialize with user context for security isolation."""
        self.session = session
        self.user_id = user_id

    async def _load_owned_lesson_and_course(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> tuple[Lesson, Course]:
        query = (
            select(Lesson, Course)
            .join(Course, Lesson.course_id == Course.id)
            .where(
                Lesson.id == lesson_id,
                Lesson.course_id == course_id,
                Course.user_id == self.user_id,
            )
        )
        result = await self.session.execute(query)
        row = result.first()

        if not row:
            logger.warning(
                "LESSON_ACCESS_DENIED",
                extra={"user_id": str(self.user_id), "lesson_id": str(lesson_id), "course_id": str(course_id)},
            )
            raise NotFoundError(
                message="Lesson not found or access denied",
                feature_area="courses",
            )

        lesson, course = row
        return lesson, course

    async def _build_course_outline_context(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> tuple[list[dict[str, Any]], int | None, int | None, str | None]:
        rows = (
            await self.session.execute(
                select(
                    Lesson.id,
                    Lesson.title,
                    Lesson.description,
                )
                .where(Lesson.course_id == course_id)
                .order_by(*Lesson.course_order_by())
            )
        ).all()

        ordered_lessons: list[dict[str, Any]] = []
        for row in rows:
            row_lesson_id, title, description = row
            ordered_lessons.append(
                {
                    "id": row_lesson_id,
                    "title": title,
                    "description": description,
                }
            )

        lesson_total = len(ordered_lessons)
        current_index = next((idx for idx, item in enumerate(ordered_lessons) if item.get("id") == lesson_id), None)
        if not isinstance(current_index, int):
            return [], None, lesson_total, None

        lesson_position = current_index + 1
        next_lesson_title = self._resolve_next_lesson_title(ordered_lessons, current_index)

        window_start = max(0, current_index - 2)
        window_end = min(lesson_total, current_index + 5)
        outline_window: list[dict[str, Any]] = []
        for idx in range(window_start, window_end):
            item = ordered_lessons[idx]
            title_value = item.get("title") or ""
            if not isinstance(title_value, str) or not title_value.strip():
                continue
            outline_window.append(
                {
                    "index": idx + 1,
                    "title": title_value,
                    "description": item.get("description") or "",
                }
            )

        return outline_window, lesson_position, lesson_total, next_lesson_title

    def _resolve_next_lesson_title(self, ordered_lessons: list[dict[str, Any]], current_index: int) -> str | None:
        next_index = current_index + 1
        if next_index >= len(ordered_lessons):
            return None
        next_title = ordered_lessons[next_index].get("title")
        if isinstance(next_title, str) and next_title.strip():
            return next_title.strip()
        return None

    async def _build_adaptive_learner_state_context(
        self,
        *,
        concept_id: uuid.UUID | None,
    ) -> str | None:
        if concept_id is None:
            return None

        concept_name = await self.session.scalar(select(Concept.name).where(Concept.id == concept_id))
        if not isinstance(concept_name, str) or not concept_name.strip():
            return None

        state = await self.session.scalar(
            select(UserConceptState).where(
                UserConceptState.user_id == self.user_id,
                UserConceptState.concept_id == concept_id,
            )
        )
        outcomes = (
            (
                await self.session.execute(
                    select(ProbeEvent.correct)
                    .where(
                        ProbeEvent.user_id == self.user_id,
                        ProbeEvent.concept_id == concept_id,
                    )
                    .order_by(ProbeEvent.ts.desc())
                    .limit(5)
                )
            )
            .scalars()
            .all()
        )

        lines = ["## Learner State", f"Concept: {concept_name.strip()}"]
        if state is None and not outcomes:
            return None

        if state is not None:
            mastery = float(state.s_mastery)
            lines.append(f"Mastery: {mastery:.2f}")

            if state.exposures > 0:
                lines.append(f"Exposures: {state.exposures}")

            if isinstance(state.learner_profile, dict):
                retention_raw = state.learner_profile.get("retention_rate")
                if isinstance(retention_raw, (int, float)):
                    lines.append(f"Retention: {float(retention_raw):.2f}")

            if state.next_review_at is not None:
                next_review_at = state.next_review_at
                if next_review_at.tzinfo is None:
                    next_review_at = next_review_at.replace(tzinfo=UTC)
                review_status = "overdue" if next_review_at < datetime.now(UTC) else "on schedule"
                lines.append(f"Review due: {review_status}")

        if outcomes:
            recent_correct = sum(1 for outcome in outcomes if outcome)
            lines.append(f"Recent probes: {recent_correct}/{len(outcomes)} correct")

        return "\n".join(lines)

    async def _build_feedback_context(
        self,
        *,
        course_id: uuid.UUID,
    ) -> str | None:
        recent_events = (
            (
                await self.session.execute(
                    select(LessonFeedbackEvent)
                    .where(LessonFeedbackEvent.course_id == course_id, LessonFeedbackEvent.apply_across_course.is_(True))
                    .order_by(LessonFeedbackEvent.created_at.desc())
                    .limit(3)
                )
            )
            .scalars()
            .all()
        )
        if not recent_events:
            return None
        lines = ["## Recent Course Feedback"] + [f"- {event.critique_text}" for event in recent_events]
        return "\n".join(lines)

    async def _build_rag_context(
        self,
        *,
        course_id: uuid.UUID,
        title: str,
        description: str,
    ) -> str:
        search_query = f"{title} {description}".strip()
        if not search_query:
            return ""

        try:
            from src.ai.rag.service import RAGService

            rag_service = RAGService()
            search_results = await rag_service.search_documents(
                session=self.session,
                user_id=self.user_id,
                course_id=course_id,
                query=search_query,
                top_k=5,
            )
            if not search_results:
                return ""

            context_parts = ["## Course Context"]
            for i, result in enumerate(search_results[:5], 1):
                context_parts.append(f"### Context {i}")
                context_parts.append(result.content)
                context_parts.append("")

            return "\n".join(context_parts).strip()
        except _LESSON_RAG_CONTEXT_FALLBACK_ERROR_TYPES:
            logger.exception(
                "Failed to get RAG context for course",
                extra={"user_id": str(self.user_id), "course_id": str(course_id)},
            )
            return ""

    def _build_outline_window_text(self, outline_window: list[dict[str, Any]]) -> str:
        if not outline_window:
            return ""

        outline_lines: list[str] = []
        for item in outline_window:
            index_value = item.get("index")
            title_value = item.get("title")
            if not isinstance(title_value, str) or not title_value:
                continue
            prefix = f"{index_value}. " if isinstance(index_value, int) else ""
            outline_lines.append(f"{prefix}{title_value}")

            item_desc = item.get("description")
            if isinstance(item_desc, str) and item_desc:
                outline_lines.append(f"Description: {item_desc}")
            outline_lines.append("")

        return "\n".join(outline_lines).strip()

    async def _build_stable_concept_objective_context(self, *, concept_id: uuid.UUID | None) -> str | None:
        if concept_id is None:
            return None

        concept = await self.session.scalar(select(Concept).where(Concept.id == concept_id))
        if concept is None:
            return None

        lines = ["## Stable Concept Objective", f"Concept: {concept.name}", "Objective:", concept.description]
        return "\n".join(lines)

    def _adaptive_pass_level(self, *, target_major_version: int) -> str:
        if target_major_version <= 2:
            return "apply_and_analyze"
        return "synthesize_and_design"

    def _previous_pass_has_stepwise_scaffolding(self, *, content: str) -> bool:
        lower_content = content.casefold()
        return any(marker in lower_content for marker in ("step 1", "step 2", "step-by-step", "worked example"))

    async def _build_course_progress_map_context(
        self,
        *,
        lesson_title: str,
        course_id: uuid.UUID,
        current_concept_id: uuid.UUID | None,
        next_lesson_title: str | None,
    ) -> tuple[str | None, bool, bool]:
        if current_concept_id is None:
            return None, False, False

        concept_rows = (
            await self.session.execute(
                select(
                    Concept.name,
                    Concept.description,
                    UserConceptState.s_mastery,
                    UserConceptState.exposures,
                )
                .select_from(CourseConcept)
                .join(Concept, Concept.id == CourseConcept.concept_id)
                .outerjoin(
                    UserConceptState,
                    and_(
                        UserConceptState.concept_id == CourseConcept.concept_id,
                        UserConceptState.user_id == self.user_id,
                    ),
                )
                .where(
                    CourseConcept.course_id == course_id,
                    CourseConcept.concept_id != current_concept_id,
                )
                .order_by(CourseConcept.order_hint.is_(None), CourseConcept.order_hint, Concept.name)
            )
        ).all()

        studied_rows: list[tuple[str, str, float, int]] = []
        future_rows: list[tuple[str, str]] = []
        for name, description, mastery, exposures in concept_rows:
            normalized_exposures = int(exposures or 0)
            if normalized_exposures > 0:
                studied_rows.append((name, description, float(mastery or 0.0), normalized_exposures))
            else:
                future_rows.append((name, description))

        lines = ["## Course Progress Map", f"Current Concept: {lesson_title}", "Studied Concepts:"]
        if studied_rows:
            for index, (name, description, mastery, exposures) in enumerate(studied_rows, start=1):
                lines.append(f"{index}. {name}")
                lines.append("Description:")
                lines.append(description)
                lines.append(f"Mastery: {mastery:.2f}")
                lines.append(f"Exposures: {exposures}")
                lines.append("")
        else:
            lines.append("None")
            lines.append("")

        lines.append("Not Yet Studied Concepts:")
        if future_rows:
            for index, (name, _description) in enumerate(future_rows, start=1):
                lines.append(f"{index}. {name}")
        else:
            lines.append("None")

        next_concept = next_lesson_title or (future_rows[0][0] if future_rows else None)
        if next_concept:
            lines.extend(["", f"Next Concept: {next_concept}"])

        return "\n".join(lines).strip(), bool(studied_rows), bool(future_rows)

    def _build_core_difficulty_ladder_context(
        self,
        *,
        lesson_title: str,
        target_major_version: int,
    ) -> str:
        lines = ["## Core Difficulty Ladder"]
        if target_major_version <= 2:
            lines.extend(
                [
                    f"- Keep every major section centered on {lesson_title}.",
                    "- Make this pass harder through more complex or compound cases of the same concept.",
                    "- Make this pass harder through multi-step reasoning, explanation, comparison, verification, or error analysis inside the same concept.",
                    "- Deepen the main move from the previous pass before branching into any extension.",
                    "- Replace full worked solutions with partial setup so the learner carries more of the execution.",
                    "- Add at least one new subtopic, edge case, or technique that still clearly belongs to the same concept and unlocks a harder use of it.",
                ]
            )
        else:
            lines.extend(
                [
                    f"- Keep every major section centered on {lesson_title}.",
                    "- Make this pass harder through synthesis, comparison, tradeoffs, or design built around the same concept.",
                    "- Use minimal scaffolding so the learner carries the central reasoning.",
                    "- Add a novel application or transfer task that still clearly belongs to the same concept.",
                    "- If you connect to other ideas, use them only to deepen the current concept instead of replacing it.",
                ]
            )

        return "\n".join(lines)

    def _build_boundary_guardrails_context(
        self,
        *,
        lesson_title: str,
        has_studied_concepts: bool,
        has_future_concepts: bool,
    ) -> str:
        lines = [
            "## Boundary Guardrails",
            f"- Keep every major section centered on {lesson_title}.",
            "- The first half of the lesson should feel like the next harder step of the previous pass, not a different lesson hiding under the same title.",
            "- Do not make the lesson harder by switching into adjacent meta-topics, style advice, or tooling unless the previous pass already centered them.",
        ]
        if has_studied_concepts:
            lines.append("- Use studied concepts only as supporting bridges and never as the main topic of a section.")
        if has_future_concepts:
            lines.append("- Do not rely on not-yet-studied concepts in the lesson body. Mention them only as a short forward pointer in the wrap-up.")
        return "\n".join(lines)

    def _build_adaptive_pass_gap_analysis_context(
        self,
        *,
        current_version: LessonVersion,
        target_major_version: int,
    ) -> str:
        lines = ["## Gap Analysis"]
        if target_major_version <= 2:
            lines.append("- The previous pass established the core idea directly; this pass must deepen it without restarting from scratch.")
        else:
            lines.append("- The previous pass already applied the concept; this pass must move into synthesis, comparison, or design-level use of the same core idea.")
        lines.append("- Carry forward the main move from the previous pass and make it harder instead of swapping it out for a neighboring idea.")

        if self._previous_pass_has_stepwise_scaffolding(content=current_version.content):
            lines.append("- The previous pass relied on step-by-step scaffolding; this pass should leave more of the execution to the learner.")
        else:
            lines.append("- Reduce scaffolding further than the previous pass and let the learner carry more of the reasoning.")

        lines.append("- Add a more formal, generalized, or comparison-driven view of the same core concept.")
        lines.append("- Add at least one compound case, explanation task, or error-analysis moment built around the same concept.")
        lines.append("- Add at least one checkpoint that requires multi-step reasoning instead of simple recall.")
        lines.append("- Introduce at least one new subtopic, edge case, or harder case that is absent from the previous pass.")

        return "\n".join(lines)

    def _build_adaptive_generation_mode_context(
        self,
        *,
        current_version: LessonVersion,
        recommendation: AdaptivePassRecommendation,
    ) -> str:
        target_major_version = current_version.major_version + 1
        lines = [
            "## Generation Mode",
            "Mode: adaptive_revisit_pass",
            f"Source Version: {current_version.major_version}.{current_version.minor_version}",
            f"Target Pass: {target_major_version}",
            f"Target Level: {self._adaptive_pass_level(target_major_version=target_major_version)}",
            f"Reason: {recommendation.reason}",
        ]
        return "\n".join(lines)

    def _build_generation_mode_context(
        self,
        *,
        generation_mode: str,
        current_version: LessonVersion | None = None,
        recommendation: AdaptivePassRecommendation | None = None,
    ) -> str:
        if generation_mode == "adaptive_revisit_pass":
            if current_version is None or recommendation is None:
                msg = "adaptive_revisit_pass requires a current version and recommendation"
                raise ValueError(msg)
            return self._build_adaptive_generation_mode_context(
                current_version=current_version,
                recommendation=recommendation,
            )

        lines = ["## Generation Mode", f"Mode: {generation_mode}"]
        return "\n".join(lines)

    def _build_pass_label(self, *, major_version: int) -> str:
        return f"Pass {major_version}"

    def _build_history_label(self, *, version: LessonVersion) -> str:
        if version.version_kind == "regeneration" or version.minor_version > 0:
            return "Regenerated"
        if version.major_version <= 1:
            return "First pass"
        return self._build_pass_label(major_version=version.major_version)

    def _build_source_reason(self, *, version: LessonVersion) -> str | None:
        metadata = version.generation_metadata if isinstance(version.generation_metadata, dict) else {}
        source_reason = metadata.get("source_reason")
        if isinstance(source_reason, str) and source_reason.strip():
            return source_reason.strip()
        if version.version_kind == "regeneration":
            return "Learner-requested rewrite of the same pass."
        if version.major_version <= 1:
            return "Initial teaching pass for this concept."
        return f"Adaptive revisit {self._build_pass_label(major_version=version.major_version).lower()}."

    def _build_previous_lesson_context(self, *, current_version: LessonVersion | None) -> str | None:
        if current_version is None:
            return None

        lines = [
            "## Previous Lesson",
            f"Version: v{current_version.major_version}.{current_version.minor_version}",
            current_version.content,
        ]
        return "\n".join(lines)

    def _append_optional_context_section(self, *, sections: list[str], section: str | None) -> None:
        if section:
            sections.append(section)

    async def _build_adaptive_pass_context_sections(
        self,
        *,
        lesson: Lesson,
        course_id: uuid.UUID,
        current_version: LessonVersion | None,
        next_lesson_title: str | None,
    ) -> list[str]:
        if current_version is None:
            msg = "adaptive_revisit_pass requires a current version"
            raise ValueError(msg)

        course_progress_map_context, has_studied_concepts, has_future_concepts = await self._build_course_progress_map_context(
            lesson_title=lesson.title,
            course_id=course_id,
            current_concept_id=lesson.concept_id,
            next_lesson_title=next_lesson_title,
        )
        target_major_version = current_version.major_version + 1

        sections = [
            self._build_core_difficulty_ladder_context(
                lesson_title=lesson.title,
                target_major_version=target_major_version,
            ),
            self._build_boundary_guardrails_context(
                lesson_title=lesson.title,
                has_studied_concepts=has_studied_concepts,
                has_future_concepts=has_future_concepts,
            ),
        ]

        self._append_optional_context_section(sections=sections, section=course_progress_map_context)
        sections.append(
            self._build_adaptive_pass_gap_analysis_context(
                current_version=current_version,
                target_major_version=target_major_version,
            )
        )

        previous_lesson_context = self._build_previous_lesson_context(current_version=current_version)
        self._append_optional_context_section(sections=sections, section=previous_lesson_context)

        return sections

    async def _select_or_create_next_pass_version(
        self,
        *,
        lesson: Lesson,
        course: Course,
        current_version: LessonVersion,
        available_versions: list[LessonVersion],
        recommendation: AdaptivePassRecommendation,
        force: bool,
        lesson_version_service: LessonVersionService,
        lesson_window_service: LessonWindowService,
    ) -> tuple[LessonVersion, list[Any]]:
        next_major_version = current_version.major_version + 1
        existing_next_pass = next(
            (version for version in available_versions if version.major_version == next_major_version),
            None,
        )
        if existing_next_pass is not None:
            selected_version = await lesson_version_service.select_current_version(
                lesson=lesson,
                version=existing_next_pass,
            )
            selected_windows = await lesson_window_service.get_or_build_windows(lesson_version=selected_version)
            return selected_version, selected_windows

        generation_recommendation = recommendation
        source_reason = recommendation.reason
        if force and recommendation.action != "deepen_with_next_major_pass":
            generation_recommendation = AdaptivePassRecommendation(
                action="deepen_with_next_major_pass",
                recommended_major_version=next_major_version,
                reason="The learner explicitly asked to start the next pass early.",
            )
            source_reason = generation_recommendation.reason

        lesson_context = await self._prepare_adaptive_pass_context(
            lesson=lesson,
            course=course,
            current_version=current_version,
            recommendation=generation_recommendation,
        )
        generated_content = await self._generate_lesson_body(lesson_context=lesson_context)
        selected_version = await lesson_version_service.create_adaptive_pass_version(
            lesson=lesson,
            content=generated_content,
            source_version=current_version,
            source_reason=source_reason,
        )
        selected_windows = await lesson_window_service.rebuild_windows(lesson_version=selected_version)
        return selected_version, selected_windows

    async def _build_generation_context_sections(
        self,
        *,
        lesson: Lesson,
        course: Course,
        generation_mode: str,
        outline_window: list[dict[str, Any]],
        lesson_position: int | None,
        lesson_total: int | None,
        next_lesson_title: str | None,
        current_version: LessonVersion | None,
        immediate_regenerate_request: str | None,
        adaptive_recommendation: AdaptivePassRecommendation | None,
    ) -> list[str]:
        context_sections: list[str] = []

        course_lines: list[str] = [f"Course: {course.title}", "Course Description:", course.description]
        context_sections.append("## Course Information\n" + "\n".join(course_lines))
        context_sections.append(
            self._build_generation_mode_context(
                generation_mode=generation_mode,
                current_version=current_version,
                recommendation=adaptive_recommendation,
            )
        )

        lesson_lines: list[str] = []
        if lesson.module_name:
            lesson_lines.append(f"Module: {lesson.module_name}")
        if isinstance(lesson_position, int) and isinstance(lesson_total, int) and lesson_total > 0:
            lesson_lines.append(f"Current lesson: {lesson_position}/{lesson_total}")
        lesson_lines.append(f"Title: {lesson.title}")
        if lesson.description:
            lesson_lines.append("Description:")
            lesson_lines.append(lesson.description)
        context_sections.append("## Lesson Focus\n" + "\n".join(lesson_lines))

        stable_objective_context = await self._build_stable_concept_objective_context(concept_id=lesson.concept_id)
        self._append_optional_context_section(sections=context_sections, section=stable_objective_context)

        if generation_mode == "adaptive_revisit_pass":
            context_sections.extend(
                await self._build_adaptive_pass_context_sections(
                    lesson=lesson,
                    course_id=course.id,
                    current_version=current_version,
                    next_lesson_title=next_lesson_title,
                )
            )
        else:
            previous_lesson_context = self._build_previous_lesson_context(current_version=current_version)
            self._append_optional_context_section(sections=context_sections, section=previous_lesson_context)

        feedback_context = await self._build_feedback_context(course_id=course.id)
        self._append_optional_context_section(sections=context_sections, section=feedback_context)

        self._append_optional_context_section(
            sections=context_sections,
            section=f"## Regeneration Request\n{immediate_regenerate_request}" if immediate_regenerate_request else None,
        )

        context_sections.append(LessonWindowService(self.session).build_generation_context(course=course))

        self._append_optional_context_section(
            sections=context_sections,
            section="## Next Lesson\n" + f"Next: {next_lesson_title}" if next_lesson_title else None,
        )

        outline_text = self._build_outline_window_text(outline_window)
        self._append_optional_context_section(
            sections=context_sections,
            section="## Course Outline (Near Term)\n" + outline_text if outline_text else None,
        )

        if course.adaptive_enabled:
            try:
                learner_state_context = await self._build_adaptive_learner_state_context(
                    concept_id=lesson.concept_id,
                )
                self._append_optional_context_section(sections=context_sections, section=learner_state_context)
            except _LESSON_LEARNER_STATE_FALLBACK_ERROR_TYPES:
                logger.exception(
                    "Failed to build adaptive learner state context",
                    extra={"user_id": str(self.user_id), "course_id": str(course.id), "lesson_id": str(lesson.id)},
                )

        return context_sections

    async def _prepare_lesson_context(
        self,
        *,
        lesson: Lesson,
        course: Course,
        generation_mode: str,
        current_version: LessonVersion | None = None,
        immediate_regenerate_request: str | None = None,
        adaptive_recommendation: AdaptivePassRecommendation | None = None,
    ) -> str:
        outline_window: list[dict[str, Any]] = []
        lesson_position: int | None = None
        lesson_total: int | None = None
        next_lesson_title: str | None = None
        try:
            outline_window, lesson_position, lesson_total, next_lesson_title = await self._build_course_outline_context(
                course_id=course.id,
                lesson_id=lesson.id,
            )
        except _LESSON_OUTLINE_FALLBACK_ERROR_TYPES:
            logger.exception(
                "Failed to build course outline context",
                extra={"user_id": str(self.user_id), "course_id": str(course.id), "lesson_id": str(lesson.id)},
            )

        context_sections = await self._build_generation_context_sections(
            lesson=lesson,
            course=course,
            generation_mode=generation_mode,
            outline_window=outline_window,
            lesson_position=lesson_position,
            lesson_total=lesson_total,
            next_lesson_title=next_lesson_title,
            current_version=current_version,
            immediate_regenerate_request=immediate_regenerate_request,
            adaptive_recommendation=adaptive_recommendation,
        )

        rag_context = await self._build_rag_context(
            course_id=course.id,
            title=lesson.title,
            description=lesson.description or "",
        )
        return "\n\n".join([*context_sections, rag_context]).strip()

    async def _prepare_regeneration_context(
        self,
        *,
        lesson: Lesson,
        course: Course,
        current_version: LessonVersion,
        critique_text: str,
    ) -> str:
        return await self._prepare_lesson_context(
            lesson=lesson,
            course=course,
            generation_mode="regeneration",
            current_version=current_version,
            immediate_regenerate_request=critique_text,
        )

    async def _prepare_adaptive_pass_context(
        self,
        *,
        lesson: Lesson,
        course: Course,
        current_version: LessonVersion,
        recommendation: AdaptivePassRecommendation,
    ) -> str:
        return await self._prepare_lesson_context(
            lesson=lesson,
            course=course,
            generation_mode="adaptive_revisit_pass",
            current_version=current_version,
            adaptive_recommendation=recommendation,
        )

    async def _generate_lesson_body(self, *, lesson_context: str) -> str:
        llm_client = LLMClient(agent_id=AGENT_ID_LESSON_WRITER)
        lesson_content = await llm_client.generate_lesson_content(
            lesson_context,
            user_id=self.user_id,
            function_tools=[build_wikipedia_resolver_function_tool()],
        )
        return lesson_content.body

    def _build_version_summaries(
        self,
        *,
        lesson: Lesson,
        versions: Sequence[LessonVersion],
    ) -> list[LessonVersionSummary]:
        return [
            LessonVersionSummary(
                id=version.id,
                major_version=version.major_version,
                minor_version=version.minor_version,
                version_kind=version.version_kind,
                version_label=f"{version.major_version}.{version.minor_version}",
                pass_label=self._build_pass_label(major_version=version.major_version),
                history_label=self._build_history_label(version=version),
                source_reason=self._build_source_reason(version=version),
                is_current=version.id == lesson.current_version_id,
                created_at=version.created_at,
            )
            for version in versions
        ]

    def _build_window_payload(self, windows: Sequence[Any]) -> list[LessonWindowResponse]:
        return [
            LessonWindowResponse(
                id=window.id,
                window_index=window.window_index,
                title=window.title,
                content=window.content,
                estimated_minutes=window.estimated_minutes,
            )
            for window in windows
        ]

    async def _recommend_next_pass(
        self,
        *,
        lesson: Lesson,
        course: Course,
        current_version: LessonVersion,
    ) -> AdaptivePassRecommendation | None:
        if not course.adaptive_enabled or lesson.concept_id is None:
            return None

        scheduler_service = LectorSchedulerService(self.session)
        return await scheduler_service.recommend_adaptive_pass(
            user_id=self.user_id,
            course_id=course.id,
            concept_id=lesson.concept_id,
            current_major_version=current_version.major_version,
        )

    async def _build_next_pass_response(
        self,
        *,
        lesson: Lesson,
        course: Course,
        current_version: LessonVersion,
        selected_version: LessonVersion,
        available_versions: Sequence[LessonVersion],
    ) -> LessonNextPassResponse | None:
        if selected_version.id != current_version.id:
            return None

        recommendation = await self._recommend_next_pass(
            lesson=lesson,
            course=course,
            current_version=current_version,
        )
        if recommendation is None:
            return None

        next_major_version = current_version.major_version + 1
        next_major_exists = any(version.major_version == next_major_version for version in available_versions)
        if next_major_exists:
            return None

        status = "recommended_now" if recommendation.action == "deepen_with_next_major_pass" else "available_early"
        return LessonNextPassResponse(
            major_version=next_major_version,
            pass_label=self._build_pass_label(major_version=next_major_version),
            status=status,
            reason=recommendation.reason,
        )

    async def _build_lesson_detail_response(
        self,
        *,
        lesson: Lesson,
        course: Course,
        selected_version: LessonVersion,
        available_versions: Sequence[LessonVersion],
        next_pass: LessonNextPassResponse | None,
        windows: Sequence[Any],
    ) -> LessonDetailResponse:
        return LessonDetailResponse(
            id=lesson.id,
            course_id=course.id,
            title=lesson.title,
            description=lesson.description,
            content=selected_version.content,
            concept_id=lesson.concept_id,
            version_id=selected_version.id,
            current_version_id=lesson.current_version_id,
            major_version=selected_version.major_version,
            minor_version=selected_version.minor_version,
            version_kind=selected_version.version_kind,
            version_label=f"{selected_version.major_version}.{selected_version.minor_version}",
            pass_label=self._build_pass_label(major_version=selected_version.major_version),
            source_reason=self._build_source_reason(version=selected_version),
            available_versions=self._build_version_summaries(lesson=lesson, versions=available_versions),
            next_pass=next_pass,
            windows=self._build_window_payload(windows),
            adaptive_enabled=course.adaptive_enabled,
            created_at=lesson.created_at,
            updated_at=lesson.updated_at,
        )

    async def get_lesson(
        self,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        force_refresh: bool = False,
        version_id: uuid.UUID | None = None,
    ) -> LessonDetailResponse:
        """Get lesson with single query including user isolation.

        Args:
            course_id: Course uuid.UUID
            lesson_id: Lesson uuid.UUID
            force_refresh: Whether to generate missing content immediately
            version_id: Optional version row to read through the same lesson route

        Returns
        -------
            LessonDetailResponse containing lesson data

        Raises
        ------
            NotFoundError: If the lesson is missing or not owned by the current user
        """
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)

        if lesson.content == "" or (force_refresh and lesson.current_version_id is None):
            lesson = await self._ensure_lesson_content(lesson, course, force_refresh=force_refresh)

        lesson_version_service = LessonVersionService(self.session)
        lesson_window_service = LessonWindowService(self.session)
        current_version = await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)
        if not (current_version.content or "").strip():
            lesson = await self._ensure_lesson_content(lesson, course, force_refresh=True)
            current_version = await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)

        selected_version = current_version
        available_versions = await lesson_version_service.list_versions(lesson=lesson)

        if version_id is not None and version_id != current_version.id:
            selected_version = await lesson_version_service.get_version(lesson=lesson, version_id=version_id)

        next_pass = await self._build_next_pass_response(
            lesson=lesson,
            course=course,
            current_version=current_version,
            selected_version=selected_version,
            available_versions=available_versions,
        )
        selected_windows = await lesson_window_service.get_or_build_windows(lesson_version=selected_version)

        return await self._build_lesson_detail_response(
            lesson=lesson,
            course=course,
            selected_version=selected_version,
            available_versions=available_versions,
            next_pass=next_pass,
            windows=selected_windows,
        )

    async def start_next_pass(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        force: bool,
    ) -> LessonDetailResponse:
        """Create or select the next major pass for one adaptive lesson."""
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)
        if not course.adaptive_enabled or lesson.concept_id is None:
            detail = "This lesson does not support adaptive passes."
            raise ConflictError(detail, feature_area="courses")

        if lesson.content == "":
            lesson = await self._ensure_lesson_content(lesson, course, force_refresh=True)

        lesson_version_service = LessonVersionService(self.session)
        lesson_window_service = LessonWindowService(self.session)
        current_version = await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)
        if not (current_version.content or "").strip():
            lesson = await self._ensure_lesson_content(lesson, course, force_refresh=True)
            current_version = await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)

        recommendation = await self._recommend_next_pass(
            lesson=lesson,
            course=course,
            current_version=current_version,
        )
        if recommendation is None:
            detail = "This lesson does not support adaptive passes."
            raise ConflictError(detail, feature_area="courses")

        if recommendation.action != "deepen_with_next_major_pass" and not force:
            detail = "The next pass is usually recommended later for this lesson."
            raise ConflictError(detail, feature_area="courses")

        available_versions = await lesson_version_service.list_versions(lesson=lesson)
        try:
            selected_version, selected_windows = await self._select_or_create_next_pass_version(
                lesson=lesson,
                course=course,
                current_version=current_version,
                available_versions=available_versions,
                recommendation=recommendation,
                force=force,
                lesson_version_service=lesson_version_service,
                lesson_window_service=lesson_window_service,
            )
        except ValueError as exc:
            detail = f"Invalid lesson content: {exc}"
            raise ValidationError(detail, feature_area="courses") from exc
        except RuntimeError as exc:
            message = "Unable to generate lesson content. Please try again."
            raise UpstreamUnavailableError(message, feature_area="courses") from exc

        await self.session.refresh(lesson)
        available_versions = await lesson_version_service.list_versions(lesson=lesson)
        next_pass = await self._build_next_pass_response(
            lesson=lesson,
            course=course,
            current_version=selected_version,
            selected_version=selected_version,
            available_versions=available_versions,
        )
        return await self._build_lesson_detail_response(
            lesson=lesson,
            course=course,
            selected_version=selected_version,
            available_versions=available_versions,
            next_pass=next_pass,
            windows=selected_windows,
        )

    async def list_lesson_versions(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LessonVersionHistoryResponse:
        """Return stable version history for one lesson."""
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)
        if lesson.content == "":
            lesson = await self._ensure_lesson_content(lesson, course)

        lesson_version_service = LessonVersionService(self.session)
        await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)
        versions = await lesson_version_service.list_versions(lesson=lesson)
        return LessonVersionHistoryResponse(versions=self._build_version_summaries(lesson=lesson, versions=versions))

    async def regenerate_lesson(
        self,
        *,
        course_id: uuid.UUID,
        lesson_id: uuid.UUID,
        critique_text: str,
        apply_across_course: bool,
    ) -> LessonDetailResponse:
        """Regenerate an existing lesson body using the normal writer path plus learner critique."""
        lesson, course = await self._load_owned_lesson_and_course(course_id=course_id, lesson_id=lesson_id)

        trimmed_critique = critique_text.strip()
        if not trimmed_critique:
            detail = "Regeneration request must not be empty"
            raise ValidationError(detail, feature_area="courses")

        try:
            lesson_version_service = LessonVersionService(self.session)
            lesson_window_service = LessonWindowService(self.session)
            current_version = await lesson_version_service.sync_current_version_from_lesson(lesson=lesson)
            available_versions = await lesson_version_service.list_versions(lesson=lesson)
            lesson_context = await self._prepare_regeneration_context(
                lesson=lesson,
                course=course,
                current_version=current_version,
                critique_text=trimmed_critique,
            )
            generated_content = await self._generate_lesson_body(lesson_context=lesson_context)
            selected_version = await lesson_version_service.create_regenerated_version(
                lesson=lesson,
                content=generated_content,
                critique_text=trimmed_critique,
            )
            feedback_event = LessonFeedbackEvent(
                course_id=course.id,
                lesson_id=lesson.id,
                lesson_version_id=current_version.id,
                critique_text=trimmed_critique,
                apply_across_course=apply_across_course,
            )
            self.session.add(feedback_event)
            await self.session.flush()
            selected_windows = await lesson_window_service.rebuild_windows(lesson_version=selected_version)
            await self.session.refresh(lesson)
        except ValueError as exc:
            detail = f"Invalid lesson content: {exc}"
            raise ValidationError(detail, feature_area="courses") from exc
        except RuntimeError as exc:
            message = "Unable to generate lesson content. Please try again."
            raise UpstreamUnavailableError(message, feature_area="courses") from exc

        available_versions = await lesson_version_service.list_versions(lesson=lesson)
        return await self._build_lesson_detail_response(
            lesson=lesson,
            course=course,
            selected_version=selected_version,
            available_versions=available_versions,
            next_pass=await self._build_next_pass_response(
                lesson=lesson,
                course=course,
                current_version=selected_version,
                selected_version=selected_version,
                available_versions=available_versions,
            ),
            windows=selected_windows,
        )

    async def _ensure_lesson_content(self, lesson: Lesson, course: Course, force_refresh: bool = False) -> Lesson:
        """Generate content for a lesson on demand."""
        _ = force_refresh
        if lesson.content != "":
            return lesson

        try:
            logger.info(
                "Generating lesson content",
                extra={
                    "user_id": str(self.user_id),
                    "lesson_id": str(lesson.id),
                    "lesson_title": lesson.title,
                },
            )
            lesson_context = await self._prepare_lesson_context(
                lesson=lesson,
                course=course,
                generation_mode="first_pass",
            )
            content = await self._generate_lesson_body(lesson_context=lesson_context)
            lesson_version_service = LessonVersionService(self.session)
            await lesson_version_service.create_initial_version(lesson=lesson, content=content)
            await self.session.refresh(lesson)
            logger.info(
                "Lesson content generated and saved",
                extra={
                    "user_id": str(self.user_id),
                    "lesson_id": str(lesson.id),
                    "content_length": len(content) if content else 0,
                },
            )

        except ValueError as exc:
            detail = f"Invalid lesson content: {exc}"
            raise ValidationError(detail, feature_area="courses") from exc
        except RuntimeError as exc:
            message = "Unable to generate lesson content. Please try again."
            raise UpstreamUnavailableError(message, feature_area="courses") from exc
        return lesson
