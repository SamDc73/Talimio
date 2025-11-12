"""Course content service for course-specific operations."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from src.ai.models import AdaptiveCoursePlan
from src.ai.service import AIService
from src.courses.models import (
    Concept,
    ConceptSimilarity,
    Course,
    CourseConcept,
    Lesson,
    UserConceptState,
)
from src.database.session import async_session_maker

from .concept_graph_service import ConceptGraphService  # type: ignore[import]


if TYPE_CHECKING:
    from fastapi import BackgroundTasks
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)

ADAPTIVE_MAX_NODES = 32
ADAPTIVE_MAX_PREREQS = 3
ADAPTIVE_MAX_LAYERS = 12
ADAPTIVE_MAX_LESSONS = 96

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _canonical_slug(value: str) -> str:
    text = (value or "").strip().lower()
    return _SLUG_PATTERN.sub("-", text).strip("-")


@dataclass(slots=True)
class AdaptiveConceptBuildResult:
    """Container for adaptive concept seeding results."""

    concept_lookup: dict[str, Concept]
    deferred_concept_ids: list[UUID] = field(default_factory=list)


class CourseContentService:
    """Course service handling course-specific content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session
        self.ai_service = AIService()

    async def create_course(
        self,
        data: dict[str, Any],
        user_id: UUID,
        session: AsyncSession | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> Course:
        """Create a new course and populate its lessons."""
        working_session = session or self.session

        if working_session is not None:
            return await self._create_course_with_session(
                working_session,
                data,
                user_id,
                background_tasks=background_tasks,
            )

        async with async_session_maker() as managed_session:
            return await self._create_course_with_session(
                managed_session,
                data,
                user_id,
                background_tasks=background_tasks,
            )

    async def _create_course_with_session(
        self,
        session: AsyncSession,
        data: dict[str, Any],
        user_id: UUID,
        *,
        background_tasks: BackgroundTasks | None = None,
    ) -> Course:
        """Create a course using the provided session."""
        session_data = dict(data)
        prompt = session_data.pop("prompt", None)
        is_adaptive = bool(session_data.get("adaptive_enabled"))
        defer_embeddings = background_tasks is not None

        adaptive_plan = await self._build_adaptive_plan(
            is_adaptive=is_adaptive,
            prompt=prompt,
            session_data=session_data,
            user_id=user_id,
        )

        modules_payload = session_data.pop("modules", [])
        lessons_payload = session_data.pop("lessons", [])

        self._serialize_payload_fields(session_data)

        course = Course(user_id=user_id, **session_data)
        session.add(course)

        try:
            await session.flush()
            normalized_modules, deferred_embedding_ids = await self._prepare_course_modules(
                session=session,
                course=course,
                adaptive_plan=adaptive_plan,
                modules_payload=modules_payload,
                lessons_payload=lessons_payload,
                defer_embeddings=defer_embeddings,
            )
            inserted_lessons = await self._insert_lessons(session, course.id, normalized_modules)
            await session.commit()
        except Exception:
            await session.rollback()
            raise

        await session.refresh(course)

        await self._handle_post_creation(
            session=session,
            course=course,
            user_id=user_id,
            deferred_embedding_ids=deferred_embedding_ids,
            background_tasks=background_tasks,
        )

        module_count = sum(1 for module in normalized_modules if module.get("title"))
        logger.info(
            "Created course %s with %d lessons across %d modules",
            course.id,
            inserted_lessons,
            module_count,
        )

        return course

    async def _build_adaptive_plan(
        self,
        *,
        is_adaptive: bool,
        prompt: str | None,
        session_data: dict[str, Any],
        user_id: UUID,
    ) -> AdaptiveCoursePlan | None:
        """Populate session data via adaptive or prompt-based generation."""
        if not is_adaptive:
            if prompt:
                generated = await self._generate_course_from_prompt(prompt, user_id)
                session_data.update(generated)
            return None

        goal_source = prompt or session_data.get("title") or ""
        clean_goal, assessment_context = self._split_goal_and_assessment(goal_source)
        goal_payload = clean_goal or goal_source or "Adaptive course outline"
        adaptive_plan = await self.ai_service.generate_adaptive_course_from_prompt(
            user_id=user_id,
            user_goal=goal_payload,
            self_assessment_context=assessment_context,
            max_nodes=ADAPTIVE_MAX_NODES,
            max_prereqs=ADAPTIVE_MAX_PREREQS,
            max_layers=ADAPTIVE_MAX_LAYERS,
            max_lessons=ADAPTIVE_MAX_LESSONS,
        )
        session_data["title"] = adaptive_plan.course.title
        session_data["description"] = adaptive_plan.ai_outline_meta.scope
        session_data["setup_commands"] = adaptive_plan.course.setup_commands
        return adaptive_plan

    def _serialize_payload_fields(self, session_data: dict[str, Any]) -> None:
        """Ensure optional payload collections are stored as JSON strings."""
        for key in ("tags", "setup_commands"):
            value = session_data.get(key)
            if value is not None:
                session_data[key] = self._ensure_json_string(value)

    async def _prepare_course_modules(
        self,
        *,
        session: AsyncSession,
        course: Course,
        adaptive_plan: AdaptiveCoursePlan | None,
        modules_payload: list[Any],
        lessons_payload: list[Any],
        defer_embeddings: bool,
    ) -> tuple[list[dict[str, Any]], list[UUID]]:
        """Return normalized modules and any deferred concept ids."""
        if adaptive_plan is None:
            normalized = self._normalize_modules_payload(modules_payload, lessons_payload)
            return (normalized, [])

        adaptive_result = await self._create_adaptive_concepts(
            session=session,
            course=course,
            plan=adaptive_plan,
            defer_embeddings=defer_embeddings,
        )
        adaptive_modules = self._build_adaptive_modules_payload(
            course=course,
            plan=adaptive_plan,
            concept_lookup=adaptive_result.concept_lookup,
        )
        normalized_modules = self._normalize_modules_payload(adaptive_modules, [])
        return (normalized_modules, adaptive_result.deferred_concept_ids)

    async def _handle_post_creation(
        self,
        *,
        session: AsyncSession,
        course: Course,
        user_id: UUID,
        deferred_embedding_ids: list[UUID],
        background_tasks: BackgroundTasks | None,
    ) -> None:
        """Kick off background work for embeddings and tagging."""
        if deferred_embedding_ids:
            if background_tasks is not None:
                self._schedule_background_embeddings(background_tasks, course.id)
            else:
                graph_service = ConceptGraphService(session)
                await graph_service.backfill_embeddings_for_course(course.id)

        try:
            if background_tasks is not None:
                self._schedule_background_tagging(background_tasks, course.id, user_id)
            else:
                await self._auto_tag_course(session, course, user_id)
        except Exception as exc:  # pragma: no cover - best-effort logging only
            logger.warning("Automatic tagging failed for course %s: %s", course.id, exc)

    def _schedule_background_embeddings(
        self,
        background_tasks: BackgroundTasks,
        course_id: UUID,
    ) -> None:
        """Enqueue background embedding generation so the response can return immediately."""
        background_tasks.add_task(self._run_background_embeddings, course_id)

    async def _run_background_embeddings(self, course_id: UUID) -> None:
        """Generate embeddings for any concepts that were deferred."""
        try:
            async with async_session_maker() as embedding_session:
                graph_service = ConceptGraphService(embedding_session)
                updated = await graph_service.backfill_embeddings_for_course(course_id)
                await embedding_session.commit()
                logger.info(
                    "Background embedding task backfilled %s concepts for course %s",
                    updated,
                    course_id,
                )
        except Exception as exc:  # pragma: no cover - best-effort background task
            logger.exception("Background embedding task failed for course %s: %s", course_id, exc)

    def _schedule_background_tagging(
        self,
        background_tasks: BackgroundTasks,
        course_id: UUID,
        user_id: UUID,
    ) -> None:
        """Enqueue background tagging so the request can return immediately."""
        background_tasks.add_task(self._run_background_auto_tagging, course_id, user_id)

    async def _run_background_auto_tagging(self, course_id: UUID, user_id: UUID) -> None:
        """Run auto-tagging in a new session after the response is sent."""
        try:
            async with async_session_maker() as tagging_session:
                course = await tagging_session.get(Course, course_id)
                if course is None:
                    logger.warning("Skipping auto-tagging for missing course %s", course_id)
                    return
                await self._auto_tag_course(tagging_session, course, user_id)
        except Exception as exc:  # pragma: no cover - background tasks are best-effort
            logger.exception("Background tagging task failed for course %s: %s", course_id, exc)

    async def update_course(
        self,
        course_id: UUID,
        data: dict[str, Any],
        user_id: UUID,
        session: AsyncSession | None = None,
    ) -> Course:
        """Update an existing course."""
        working_session = session or self.session
        if working_session is not None:
            return await self._update_course_with_session(
                working_session,
                course_id,
                data,
                user_id,
                commit=False,
            )

        async with async_session_maker() as managed_session:
            return await self._update_course_with_session(
                managed_session,
                course_id,
                data,
                user_id,
                commit=True,
            )

    async def _update_course_with_session(
        self,
        session: AsyncSession,
        course_id: UUID,
        data: dict[str, Any],
        user_id: UUID,
        *,
        commit: bool,
    ) -> Course:
        query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
        result = await session.execute(query)
        course = result.scalar_one_or_none()
        if not course:
            error_msg = f"Course {course_id} not found"
            raise ValueError(error_msg)

        for attr, value in data.items():
            if value is None:
                continue
            if attr in {"tags", "setup_commands"}:
                setattr(course, attr, self._ensure_json_string(value))
                continue
            setattr(course, attr, value)

        course.updated_at = datetime.now(UTC)

        await session.flush()
        if commit:
            await session.commit()
        await session.refresh(course)
        return course

    async def _auto_tag_course(self, session: AsyncSession, course: Course, user_id: UUID) -> list[str]:
        """Generate tags for a course using its content preview and persist them."""
        try:
            from src.tagging.processors.course_processor import process_course_for_tagging
            from src.tagging.service import TaggingService

            content_data = await process_course_for_tagging(str(course.id), session)
            if not content_data:
                logger.warning("Course %s not found or contains no content for tagging", course.id)
                return []

            tagging_service = TaggingService(session)
            tags = await tagging_service.tag_content(
                content_id=course.id,
                content_type="course",
                user_id=user_id,
                title=content_data.get("title", ""),
                content_preview=content_data.get("content_preview", ""),
            )

            if tags:
                course.tags = json.dumps(tags)
                await session.commit()

            return tags or []
        except Exception as exc:
            logger.exception("Auto-tagging error for course %s: %s", course.id, exc)
            return []

    async def _insert_lessons(
        self,
        session: AsyncSession,
        course_id: UUID,
        modules: list[dict[str, Any]],
    ) -> int:
        """Insert lessons for a course based on normalized module payload."""
        lesson_rows: list[dict[str, Any]] = []
        timestamp = datetime.now(UTC)

        for module_index, module in enumerate(modules):
            module_title = module.get("title")
            module_name = module_title.strip() if isinstance(module_title, str) and module_title.strip() else None
            module_order = module_index if module_name is not None else None
            raw_lessons = module.get("lessons", [])

            if not isinstance(raw_lessons, list):
                raw_lessons = [raw_lessons]

            for lesson_index, payload in enumerate(raw_lessons):
                if not isinstance(payload, dict):
                    continue

                title = payload.get("title") or f"Lesson {lesson_index + 1}"
                description = payload.get("description") or ""
                content = payload.get("content") or payload.get("body") or payload.get("markdown") or ""
                order_value = payload.get("order")
                lesson_order = int(order_value) if isinstance(order_value, int) else lesson_index

                lesson_id_value = payload.get("id")
                lesson_uuid: UUID | None = None
                if lesson_id_value is not None:
                    try:
                        lesson_uuid = lesson_id_value if isinstance(lesson_id_value, UUID) else UUID(str(lesson_id_value))
                    except (TypeError, ValueError):
                        logger.warning(
                            "Ignoring invalid lesson id override %s for course %s",
                            lesson_id_value,
                            course_id,
                        )

                slug_value = payload.get("slug")
                if lesson_uuid is None and isinstance(slug_value, str) and slug_value.strip():
                    slug_text = slug_value.strip().lower()
                    try:
                        lesson_uuid = uuid5(NAMESPACE_URL, f"outline-lesson:{course_id}:{slug_text}")
                    except Exception:  # pragma: no cover - uuid5 should not fail, but guard anyway
                        logger.warning("Failed to derive deterministic id from slug %s for course %s", slug_value, course_id)

                lesson_kwargs: dict[str, Any] = {
                    "course_id": course_id,
                    "title": title,
                    "description": description,
                    "content": content,
                    "order": lesson_order,
                    "module_name": module_name,
                    "module_order": module_order,
                    "created_at": timestamp,
                    "updated_at": timestamp,
                }
                if lesson_uuid is not None:
                    lesson_kwargs["id"] = lesson_uuid

                lesson_rows.append(lesson_kwargs)

        if not lesson_rows:
            return 0

        stmt = insert(Lesson).values(lesson_rows)
        await session.execute(stmt)
        return len(lesson_rows)

    def _normalize_modules_payload(
        self,
        modules: list[Any],
        lessons: list[Any],
    ) -> list[dict[str, Any]]:
        """Normalize modules/lessons with the simplest acceptable shape."""
        # Prefer explicit modules with a proper lessons list
        if isinstance(modules, list) and modules:
            normalized: list[dict[str, Any]] = []
            for module in modules:
                if not isinstance(module, dict):
                    continue
                ml = module.get("lessons")
                if isinstance(ml, list) and ml:
                    normalized.append(
                        {
                            "title": module.get("title"),
                            "description": module.get("description"),
                            "lessons": ml,
                        }
                    )
            if normalized:
                return normalized

        # Fallback: a flat lessons list becomes a single unnamed module
        if isinstance(lessons, list) and lessons:
            return [{"title": None, "description": None, "lessons": lessons}]

        # Nothing to insert
        return []

    async def _create_adaptive_concepts(
        self,
        *,
        session: AsyncSession,
        course: Course,
        plan: AdaptiveCoursePlan,
        defer_embeddings: bool,
    ) -> AdaptiveConceptBuildResult:
        """Persist adaptive concept metadata derived from a precomputed plan and return a slug map."""
        graph_service = ConceptGraphService(session)
        concept_graph = plan.ai_outline_meta.concept_graph

        layer_lookup = plan.layer_index()
        concept_lookup: dict[str, Concept] = {}
        state_rows: list[dict[str, Any]] = []
        course_concept_rows: list[dict[str, Any]] = []
        concept_order: list[str] = []
        deferred_concept_ids: list[UUID] = []

        for index, node in enumerate(concept_graph.nodes):
            slug_source = node.slug or node.title
            slug_text = _canonical_slug(slug_source)
            if not slug_text:
                msg = f"Adaptive plan provided an empty slug for concept index {index}"
                raise ValueError(msg)
            if slug_text in concept_lookup:
                msg = f"Duplicate concept slug detected in adaptive plan: {slug_text}"
                raise ValueError(msg)

            layer_index = layer_lookup.get(slug_text)
            difficulty = min(5, layer_index + 1) if layer_index is not None else None
            description = self._build_concept_description(node.title, plan.concept_tags_for(slug_text))

            concept = await graph_service.create_concept(
                domain=course.title,
                name=node.title,
                description=description,
                slug=slug_text,
                difficulty=difficulty,
                generate_embedding=not defer_embeddings,
            )
            if defer_embeddings:
                deferred_concept_ids.append(concept.id)
            course_concept_rows.append(
                {
                    "course_id": course.id,
                    "concept_id": concept.id,
                    "order_hint": index,
                }
            )
            concept_lookup[slug_text] = concept
            concept_order.append(slug_text)

            if node.initial_mastery is not None:
                state_rows.append(
                    {
                        "user_id": course.user_id,
                        "concept_id": concept.id,
                        "s_mastery": float(node.initial_mastery),
                    }
                )

        if course_concept_rows:
            concept_stmt = (
                insert(CourseConcept)
                .values(course_concept_rows)
                .on_conflict_do_nothing()
            )
            await session.execute(concept_stmt.execution_options(insertmanyvalues_page_size=250))

        await session.flush()

        seeded_state_count = await self._seed_owner_states(session=session, state_rows=state_rows)
        confusor_pair_count = await self._persist_confusors(
            session=session,
            concept_graph=concept_graph,
            concept_lookup=concept_lookup,
            course_id=course.id,
        )

        logger.info(
            "Adaptive concept seeding for course %s persisted %d user states and %d confusor pairs",
            course.id,
            seeded_state_count,
            confusor_pair_count,
        )

        edge_pairs: list[tuple[UUID, UUID]] = []
        for edge in concept_graph.edges:
            source_slug = _canonical_slug(edge.source_slug)
            prereq_slug = _canonical_slug(edge.prereq_slug)
            dependent = concept_lookup.get(source_slug)
            prerequisite = concept_lookup.get(prereq_slug)
            if dependent is None or prerequisite is None:
                logger.warning(
                    "Skipping edge due to unknown nodes: %s depends on %s",
                    edge.source_slug,
                    edge.prereq_slug,
                )
                continue
            edge_pairs.append((dependent.id, prerequisite.id))

        inserted_edges = await graph_service.add_prerequisites_bulk(edge_pairs)
        logger.info(
            "Adaptive concept graph inserted %d prerequisite edges for course %s",
            inserted_edges,
            course.id,
        )

        return AdaptiveConceptBuildResult(
            concept_lookup=concept_lookup,
            deferred_concept_ids=deferred_concept_ids,
        )

    async def _seed_owner_states(
        self,
        *,
        session: AsyncSession,
        state_rows: list[dict[str, Any]],
    ) -> int:
        if not state_rows:
            return 0
        state_stmt = insert(UserConceptState).values(state_rows).on_conflict_do_nothing()
        await session.execute(state_stmt)
        return len(state_rows)

    async def _persist_confusors(
        self,
        *,
        session: AsyncSession,
        concept_graph: Any,
        concept_lookup: dict[str, Concept],
        course_id: UUID,
    ) -> int:
        confusor_pairs: dict[tuple[UUID, UUID], float] = {}
        for confusor_set in concept_graph.confusors:
            base_slug = _canonical_slug(confusor_set.slug)
            base_concept = concept_lookup.get(base_slug)
            if base_concept is None:
                logger.warning("Skipping confusor set due to unknown concept slug: %s", confusor_set.slug)
                continue
            for confusor in confusor_set.confusors:
                other_slug = _canonical_slug(confusor.slug)
                other_concept = concept_lookup.get(other_slug)
                if other_concept is None:
                    logger.warning("Skipping confusor pair due to unknown concept slug: %s", confusor.slug)
                    continue
                if base_concept.id == other_concept.id:
                    continue
                base_id = base_concept.id
                other_id = other_concept.id
                ordered: tuple[UUID, UUID] = (
                    (base_id, other_id) if str(base_id) < str(other_id) else (other_id, base_id)
                )
                risk_value = float(confusor.risk)
                current = confusor_pairs.get(ordered)
                if current is None or risk_value > current:
                    confusor_pairs[ordered] = risk_value

        if not confusor_pairs:
            # TODO(pgvector-fallback): derive similarity pairs from embeddings when the LLM omits confusors.
            logger.debug("No LLM confusors provided for adaptive course %s", course_id)
            return 0

        now = datetime.now(UTC)
        stmt = (
            insert(ConceptSimilarity)
            .values(
                [
                    {
                        "concept_a_id": pair[0],
                        "concept_b_id": pair[1],
                        "similarity": similarity,
                        "computed_at": now,
                    }
                    for pair, similarity in confusor_pairs.items()
                ]
            )
            .on_conflict_do_nothing()
        )
        await session.execute(stmt)
        return len(confusor_pairs)

    def _build_adaptive_modules_payload(
        self,
        *,
        course: Course,
        plan: AdaptiveCoursePlan,
        concept_lookup: dict[str, Concept],
    ) -> list[dict[str, Any]]:
        """Return module payload (pre-normalization) derived from adaptive concepts."""
        lessons = self._build_adaptive_lessons_payload(
            course=course,
            plan=plan,
            concept_lookup=concept_lookup,
        )
        if not lessons:
            logger.warning("Adaptive plan for course %s produced no lesson payloads", course.id)
            return []

        module_description = (plan.ai_outline_meta.scope or "").strip()
        if not module_description:
            module_description = f"Adaptive pathway for {course.title}"

        return [
            {
                "title": "Adaptive Track",
                "description": module_description,
                "lessons": lessons,
            }
        ]

    def _build_adaptive_lessons_payload(
        self,
        *,
        course: Course,
        plan: AdaptiveCoursePlan,
        concept_lookup: dict[str, Concept],
    ) -> list[dict[str, Any]]:
        """Build deterministic lesson payloads for adaptive concepts."""
        lessons: list[dict[str, Any]] = []
        assigned: set[UUID] = set()

        for index, lesson_plan in enumerate(plan.lessons):
            slug = _canonical_slug(lesson_plan.slug)
            concept = concept_lookup.get(slug)
            if concept is None:
                logger.debug("Skipping unknown adaptive lesson slug '%s' for course %s", slug, course.id)
                continue

            lesson_id = uuid5(NAMESPACE_URL, f"concept-lesson:{course.id}:{concept.id}")
            lessons.append(
                {
                    "id": lesson_id,
                    "title": lesson_plan.title or concept.name,
                    "description": lesson_plan.description
                    or lesson_plan.objective
                    or concept.description,
                    "content": "",
                    "order": index,
                }
            )
            assigned.add(concept.id)

        order_cursor = len(lessons)
        for concept in concept_lookup.values():
            if concept.id in assigned:
                continue

            lesson_id = uuid5(NAMESPACE_URL, f"concept-lesson:{course.id}:{concept.id}")
            lessons.append(
                {
                    "id": lesson_id,
                    "title": concept.name,
                    "description": concept.description,
                    "content": "",
                    "order": order_cursor,
                }
            )
            order_cursor += 1

        return lessons

    def _split_goal_and_assessment(self, text: str) -> tuple[str, str | None]:
        """Extract self-assessment from user goal text."""
        if not isinstance(text, str):
            return ("", None)
        marker = "self-assessment:"
        lower = text.lower()
        idx = lower.rfind(marker)
        if idx == -1:
            return (text.strip(), None)
        base = text[:idx].strip()
        assessment = text[idx:].strip()
        return (base or text.strip(), assessment or None)

    def _build_concept_description(self, title: str, tags: list[str]) -> str:
        """Compose a concise description from title and tags."""
        clean_title = title.strip()
        parts = [clean_title] if clean_title else []
        clean_tags = [tag.strip() for tag in tags if tag.strip()]
        if clean_tags:
            parts.append(f"Tags: {', '.join(clean_tags)}")
        return " — ".join(parts) if parts else clean_title

    @staticmethod
    def _normalize_module_name(raw_value: Any) -> str | None:
        if raw_value is None:
            return None
        text = str(raw_value).strip()
        return text or None

    def _module_description_from_goals(self, module_name: str | None, module_goals: Any) -> str | None:
        if not module_name or not isinstance(module_goals, dict):
            return None
        candidate = module_goals.get(module_name)
        if candidate is None:
            lowered = module_name.lower()
            for key, value in module_goals.items():
                if isinstance(key, str) and key.lower() == lowered:
                    candidate = value
                    break
        if candidate is None:
            return None
        if isinstance(candidate, str):
            text = candidate.strip()
            return text or None
        if isinstance(candidate, list):
            parts = [str(item).strip() for item in candidate if str(item).strip()]
            if parts:
                return " • ".join(parts)
        return None

    def _build_modules_from_outline(self, lessons: list[Any], module_goals: Any) -> list[dict[str, Any]]:
        if not lessons:
            return []
        module_map: dict[str, dict[str, Any]] = {}
        for lesson in lessons:
            raw_title = getattr(lesson, "title", None)
            if raw_title is None and isinstance(lesson, dict):
                raw_title = lesson.get("title")
            title = str(raw_title or "").strip()
            if not title:
                continue
            raw_description = getattr(lesson, "description", None)
            if raw_description is None and isinstance(lesson, dict):
                raw_description = lesson.get("description")
            description = str(raw_description or "").strip()
            module_value = getattr(lesson, "module", None)
            if module_value is None and isinstance(lesson, dict):
                module_value = lesson.get("module")
            module_name = self._normalize_module_name(module_value)
            module_key = module_name or "__default__"
            module_entry = module_map.get(module_key)
            if module_entry is None:
                module_entry = {
                    "title": module_name,
                    "description": self._module_description_from_goals(module_name, module_goals),
                    "lessons": [],
                }
                module_map[module_key] = module_entry
            raw_content = getattr(lesson, "content", None)
            if raw_content is None and isinstance(lesson, dict):
                raw_content = lesson.get("content") or lesson.get("body") or lesson.get("markdown")
            lesson_slug = getattr(lesson, "slug", None)
            if lesson_slug is None and isinstance(lesson, dict):
                lesson_slug = lesson.get("slug")
            prereq_slugs = getattr(lesson, "prereq_slugs", None)
            if prereq_slugs is None and isinstance(lesson, dict):
                prereq_slugs = lesson.get("prereq_slugs")
            lessons_list = cast("list[dict[str, Any]]", module_entry.setdefault("lessons", []))
            if not isinstance(lessons_list, list):
                lessons_list = []
                module_entry["lessons"] = lessons_list
            lessons_list.append(
                {
                    "title": title,
                    "description": description,
                    "content": raw_content or "",
                    "slug": lesson_slug,
                    "prereq_slugs": prereq_slugs if isinstance(prereq_slugs, list) else [],
                }
            )
        return list(module_map.values())

    def _ensure_json_string(self, value: Any) -> str:
        """Ensure value is serialized to a JSON string."""
        if isinstance(value, str):
            return value
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value))
        try:
            return json.dumps(value)
        except Exception:
            return json.dumps(str(value))

    async def _generate_course_from_prompt(
        self,
        prompt: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Generate course data from AI prompt."""
        ai_result = await self.ai_service.course_generate(
            user_id=user_id,
            topic=prompt,
        )
        if not ai_result:
            error_msg = "Invalid AI response format for course generation"
            raise TypeError(error_msg)

        course_meta = getattr(ai_result, "course", None)
        if course_meta is None:
            error_msg = "AI generation returned no course metadata"
            raise RuntimeError(error_msg)

        title = course_meta.title
        description = (
            course_meta.description
            or (ai_result.ai_outline_meta or {}).get("scope")
            or f"A course about {prompt}"
        )
        module_goals = {}
        if isinstance(ai_result.ai_outline_meta, dict):
            raw_module_goals = ai_result.ai_outline_meta.get("moduleGoals")
            if isinstance(raw_module_goals, dict):
                module_goals = raw_module_goals

        modules = self._build_modules_from_outline(list(ai_result.lessons or []), module_goals)
        if not modules:
            logger.warning("AI generated no lessons for prompt '%s'", prompt)

        result: dict[str, Any] = {
            "title": title,
            "description": description,
            "tags": [],
            "setup_commands": course_meta.setup_commands,
            "modules": modules,
        }

        return result
