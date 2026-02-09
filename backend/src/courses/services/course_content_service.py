"""Course content service for course-specific operations."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import DateTime, Float, Integer, bindparam, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY, UUID as PGUUID, insert

from src.ai.models import AdaptiveCourseStructure
from src.ai.rag.service import RAGService
from src.ai.service import AIService
from src.auth import AuthContext
from src.courses.models import (
    Concept,
    Course,
    Lesson,
)
from src.database.session import async_session_maker

from .concept_graph_service import ConceptGraphService


if TYPE_CHECKING:
    from fastapi import BackgroundTasks, UploadFile
    from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)
_DETACHED_TASKS: set[asyncio.Task[Any]] = set()

_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")
_DOC_EXTENSIONS = {".pdf", ".epub"}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


def _canonical_slug(value: str) -> str:
    text = (value or "").strip().lower()
    return _SLUG_PATTERN.sub("-", text).strip("-")


def _spawn_detached_task(coro: Coroutine[Any, Any, None]) -> None:
    """Run background work outside FastAPI response-bound BackgroundTasks."""
    task = asyncio.create_task(coro)
    _DETACHED_TASKS.add(task)
    task.add_done_callback(_DETACHED_TASKS.discard)


@dataclass(slots=True)
class AdaptiveConceptBuildResult:
    """Container for adaptive concept seeding results."""

    concepts_by_index: list[Concept]


class CourseContentService:
    """Course service handling course-specific content operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.ai_service = AIService()

    async def create_course(
        self,
        data: dict[str, Any],
        user_id: UUID,
        background_tasks: BackgroundTasks | None = None,
        attachments: list[UploadFile] | None = None,
    ) -> Course:
        """Create a new course and populate its lessons."""
        return await self._create_course_with_session(
            self.session,
            data,
            user_id,
            background_tasks=background_tasks,
            attachments=attachments,
        )

    async def _create_course_with_session(
        self,
        session: AsyncSession,
        data: dict[str, Any],
        user_id: UUID,
        *,
        background_tasks: BackgroundTasks | None = None,
        attachments: list[UploadFile] | None = None,
    ) -> Course:
        """Create a course using the provided session."""
        session_data = dict(data)
        is_adaptive = bool(session_data.get("adaptive_enabled"))

        draft_title = str(session_data.get("title") or "Draft course")
        draft_description = str(session_data.get("description") or "Draft course description")
        course = Course(
            user_id=user_id,
            title=draft_title,
            description=draft_description,
            adaptive_enabled=is_adaptive,
            archived=bool(session_data.get("archived", False)),
        )
        session.add(course)
        await session.flush()

        prompt = session_data.pop("prompt", None)
        prompt_text = self._normalize_prompt_text(prompt)
        attachments = attachments or []
        normalized_modules: list[dict[str, Any]] = []
        inserted_lessons = 0

        rag_service = RAGService()
        auth = AuthContext(user_id=user_id, session=session)
        image_data_urls = await self._ingest_course_attachments(
            rag_service=rag_service,
            auth=auth,
            course_id=course.id,
            attachments=attachments,
        )
        augmented_prompt = await self._build_augmented_prompt(
            rag_service=rag_service,
            auth=auth,
            course_id=course.id,
            prompt_text=prompt_text,
        )
        prompt_payload = self._build_prompt_payload(augmented_prompt, image_data_urls)

        adaptive_structure = await self._build_adaptive_structure(
            is_adaptive=is_adaptive,
            prompt=prompt_payload,
            prompt_text=prompt_text,
            session_data=session_data,
            user_id=user_id,
        )

        modules_payload = session_data.pop("modules", [])
        lessons_payload = session_data.pop("lessons", [])

        self._serialize_payload_fields(session_data)
        self._apply_course_updates(course, session_data)

        normalized_modules = await self._prepare_course_modules(
            session=session,
            course=course,
            adaptive_structure=adaptive_structure,
            modules_payload=modules_payload,
            lessons_payload=lessons_payload,
        )
        inserted_lessons = await self._insert_lessons(session, course.id, normalized_modules)
        if background_tasks is not None:
            # Ensure background tasks can read committed course/lesson rows.
            await session.commit()
        else:
            await session.flush()

        await session.refresh(course)

        await self._handle_post_creation(
            session=session,
            course=course,
            user_id=user_id,
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

    async def _build_adaptive_structure(
        self,
        *,
        is_adaptive: bool,
        prompt: str | list[dict[str, Any]] | None,
        prompt_text: str,
        session_data: dict[str, Any],
        user_id: UUID,
    ) -> AdaptiveCourseStructure | None:
        """Populate session data via adaptive or prompt-based generation."""
        if not is_adaptive:
            if prompt:
                generated = await self._generate_course_from_prompt(prompt, prompt_text, user_id)
                session_data.update(generated)
            return None

        goal_source = prompt_text or session_data.get("title") or ""
        goal_payload = str(goal_source).strip() or "Adaptive course outline"
        user_prompt_payload = prompt if prompt else goal_payload
        adaptive_structure = await self.ai_service.generate_adaptive_course_structure(
            user_id=user_id,
            user_prompt=user_prompt_payload,
        )
        session_data["title"] = adaptive_structure.course.title
        session_data["description"] = adaptive_structure.ai_outline_meta.scope
        session_data["setup_commands"] = adaptive_structure.course.setup_commands
        return adaptive_structure

    def _serialize_payload_fields(self, session_data: dict[str, Any]) -> None:
        """Ensure optional payload collections are stored as JSON strings."""
        for key in ("tags", "setup_commands"):
            value = session_data.get(key)
            if value is not None:
                session_data[key] = self._ensure_json_string(value)

    def _normalize_prompt_text(self, prompt: Any) -> str:
        """Normalize prompt input into a trimmed string."""
        if prompt is None:
            return ""
        return str(prompt).strip()

    async def _ingest_course_attachments(
        self,
        *,
        rag_service: RAGService,
        auth: AuthContext,
        course_id: UUID,
        attachments: list[UploadFile],
    ) -> list[str]:
        """Upload attachments and return image data URLs."""
        image_data_urls: list[str] = []
        for attachment in attachments:
            raw_filename = attachment.filename or "attachment"
            filename = Path(raw_filename).name
            extension = Path(filename).suffix.lower()
            file_content = await attachment.read()
            if extension in _DOC_EXTENSIONS:
                document_type = extension.lstrip(".")
                document = await rag_service.upload_document(
                    auth=auth,
                    course_id=course_id,
                    document_type=document_type,
                    title=filename,
                    file_content=file_content,
                    filename=filename,
                    process_in_background=False,
                )
                await rag_service.process_document(auth.session, document.id)
                continue
            if extension in _IMAGE_EXTENSIONS:
                data_url = self._build_image_data_url(file_content, attachment.content_type, extension)
                image_data_urls.append(data_url)
                await rag_service.upload_document(
                    auth=auth,
                    course_id=course_id,
                    document_type="image",
                    title=filename,
                    file_content=file_content,
                    filename=filename,
                    process_in_background=False,
                )
        return image_data_urls

    async def _build_augmented_prompt(
        self,
        *,
        rag_service: RAGService,
        auth: AuthContext,
        course_id: UUID,
        prompt_text: str,
    ) -> str:
        """Append RAG context to the prompt if available."""
        if not prompt_text:
            return ""
        results = await rag_service.search_documents(auth, course_id, query=prompt_text, top_k=5)
        chunks = [result.content for result in results if result.content]
        if not chunks:
            return prompt_text
        context_block = "\n\nReference Context:\n" + "\n\n".join(chunks)
        return f"{prompt_text}{context_block}"

    def _build_prompt_payload(self, prompt_text: str, image_data_urls: list[str]) -> str | list[dict[str, Any]]:
        """Return a multimodal prompt payload when images are present."""
        if not image_data_urls:
            return prompt_text
        image_parts = [{"type": "image_url", "image_url": {"url": url}} for url in image_data_urls]
        return [{"type": "text", "text": prompt_text}, *image_parts]

    def _build_image_data_url(self, file_content: bytes, content_type: str | None, extension: str) -> str:
        """Build a base64 data URL for image inputs."""
        mime_type = content_type
        if not mime_type:
            mime_type = "image/png" if extension == ".png" else "image/jpeg"
        encoded = base64.b64encode(file_content).decode("utf-8")
        return f"data:{mime_type};base64,{encoded}"

    def _apply_course_updates(self, course: Course, session_data: dict[str, Any]) -> None:
        """Apply generated payload fields to the draft course."""
        for key in ("title", "description", "tags", "setup_commands", "adaptive_enabled", "archived"):
            if key in session_data and session_data[key] is not None:
                setattr(course, key, session_data[key])

    async def _prepare_course_modules(
        self,
        *,
        session: AsyncSession,
        course: Course,
        adaptive_structure: AdaptiveCourseStructure | None,
        modules_payload: list[Any],
        lessons_payload: list[Any],
    ) -> list[dict[str, Any]]:
        """Return normalized modules."""
        if adaptive_structure is None:
            return self._normalize_modules_payload(modules_payload, lessons_payload)

        adaptive_result = await self._create_adaptive_concepts(
            session=session,
            course=course,
            plan=adaptive_structure,
        )
        adaptive_modules = self._build_adaptive_modules_payload(
            course=course,
            plan=adaptive_structure,
            concepts_by_index=adaptive_result.concepts_by_index,
        )
        return self._normalize_modules_payload(adaptive_modules, [])

    async def _handle_post_creation(
        self,
        *,
        session: AsyncSession,
        course: Course,
        user_id: UUID,
        background_tasks: BackgroundTasks | None,
    ) -> None:
        """Kick off background work for embeddings and tagging."""
        if course.adaptive_enabled:
            await self._handle_adaptive_embeddings(
                session=session,
                course_id=course.id,
                background_tasks=background_tasks,
            )

        try:
            if background_tasks is not None:
                self._schedule_background_tagging(course.id, user_id)
            else:
                await self._auto_tag_course(session, course, user_id)
        except Exception as exc:
            logger.warning("Automatic tagging failed for course %s: %s", course.id, exc)

    def _schedule_background_embeddings(
        self,
        course_id: UUID,
    ) -> None:
        """Enqueue background embedding generation so the response can return immediately."""
        _spawn_detached_task(self._run_background_embeddings(course_id))

    async def _handle_adaptive_embeddings(
        self,
        *,
        session: AsyncSession,
        course_id: UUID,
        background_tasks: BackgroundTasks | None,
    ) -> None:
        if background_tasks is not None:
            self._schedule_background_embeddings(course_id)
            return
        await self._run_embedding_pipeline(session, course_id)

    async def _run_embedding_pipeline(
        self,
        session: AsyncSession,
        course_id: UUID,
    ) -> tuple[int, int]:
        graph_service = ConceptGraphService(session)
        updated = await graph_service.backfill_embeddings_for_course(course_id)
        try:
            pairs = await graph_service.recompute_embedding_confusors_for_course(course_id)
        except Exception as conf_exc:
            logger.exception("Confusor recompute failed for course %s: %s", course_id, conf_exc)
            pairs = 0
        await session.flush()
        return updated, pairs

    async def _run_background_embeddings(self, course_id: UUID) -> None:
        """Generate embeddings for any concepts that were deferred and compute confusors.

        Runs both steps in a single background task to ensure confusor computation
        sees finalized embeddings.
        """
        try:
            async with async_session_maker() as embedding_session:
                updated, pairs = await self._run_embedding_pipeline(embedding_session, course_id)
                await embedding_session.commit()
                logger.info(
                    "Background embedding task backfilled %s concepts and computed %s confusor pairs for course %s",
                    updated,
                    pairs,
                    course_id,
                )
        except Exception as exc:  # pragma: no cover - best-effort background task
            logger.exception("Background embedding task failed for course %s: %s", course_id, exc)

    def _schedule_background_tagging(
        self,
        course_id: UUID,
        user_id: UUID,
    ) -> None:
        """Enqueue background tagging so the request can return immediately."""
        _spawn_detached_task(self._run_background_auto_tagging(course_id, user_id))

    async def _run_background_auto_tagging(self, course_id: UUID, user_id: UUID) -> None:
        """Run auto-tagging in a new session after the response is sent."""
        try:
            async with async_session_maker() as tagging_session:
                course = await tagging_session.get(Course, course_id)
                if course is None:
                    logger.warning("Skipping auto-tagging for missing course %s", course_id)
                    return
                await self._auto_tag_course(tagging_session, course, user_id)
                await tagging_session.commit()
        except Exception as exc:
            logger.exception("Background tagging task failed for course %s: %s", course_id, exc)

    async def update_course(
        self,
        course_id: UUID,
        data: dict[str, Any],
        user_id: UUID,
    ) -> Course:
        """Update an existing course."""
        return await self._update_course_with_session(
            self.session,
            course_id,
            data,
            user_id,
        )

    async def _update_course_with_session(
        self,
        session: AsyncSession,
        course_id: UUID,
        data: dict[str, Any],
        user_id: UUID,
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
        await session.refresh(course)
        return course

    async def _auto_tag_course(self, session: AsyncSession, course: Course, user_id: UUID) -> list[str]:
        """Generate and persist tags for a course.

        Uses SQLAlchemy Core UPDATE to avoid ORM stale update errors when the row
        is concurrently deleted/updated while keeping commit/rollback ownership
        in the caller.
        """
        course_id_str = str(course.id)
        try:
            from src.tagging.processors.course_processor import process_course_for_tagging
            from src.tagging.service import TaggingService

            # Re-extract content from DB by id to ensure the course still exists
            content_data = await process_course_for_tagging(course.id, user_id, session)
            if not content_data:
                logger.info("Skipping auto-tagging for missing/empty course %s", course_id_str)
                return []

            tagging_service = TaggingService(session)
            tags = await tagging_service.tag_content(
                content_id=course.id,
                content_type="course",
                user_id=user_id,
                title=content_data.get("title", ""),
                content_preview=content_data.get("content_preview", ""),
            )

            if not tags:
                return []

            # Double-check existence to avoid orphan tag associations if the course disappeared after tag generation.
            exists_result = await session.execute(select(Course.id).where(Course.id == course.id))
            if exists_result.scalar_one_or_none() is None:
                await session.execute(
                    text(
                        """
                        DELETE FROM tag_associations
                        WHERE content_id = :content_id
                          AND content_type = 'course'
                          AND user_id = :user_id
                        """
                    ),
                    {"content_id": str(course.id), "user_id": str(user_id)},
                )
                await session.flush()
                logger.info("Skipping tag persist for deleted course %s", course_id_str)
                return []

            # Persist tags via a Core UPDATE to avoid ORM StaleDataError on flush
            update_stmt = update(Course).where(Course.id == course.id).values(tags=json.dumps(tags))
            upd_result = await session.execute(update_stmt)

            # If the row vanished between the existence check and UPDATE, drop tag associations from this run.
            if getattr(upd_result, "rowcount", 0) == 0:
                await session.execute(
                    text(
                        """
                        DELETE FROM tag_associations
                        WHERE content_id = :content_id
                          AND content_type = 'course'
                          AND user_id = :user_id
                        """
                    ),
                    {"content_id": str(course.id), "user_id": str(user_id)},
                )
                await session.flush()
                logger.info("Course %s disappeared before update; tags not saved", course_id_str)
                return []

            await session.flush()
            return tags
        except Exception as exc:
            logger.exception("Auto-tagging error for course %s: %s", course_id_str, exc)
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
                content = ""
                order_value = payload.get("order")
                lesson_order = int(order_value) if isinstance(order_value, int) else lesson_index

                lesson_id_value = payload.get("id")
                lesson_uuid: UUID | None = None
                if lesson_id_value is not None:
                    try:
                        lesson_uuid = (
                            lesson_id_value if isinstance(lesson_id_value, UUID) else UUID(str(lesson_id_value))
                        )
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
                        logger.warning(
                            "Failed to derive deterministic id from slug %s for course %s", slug_value, course_id
                        )

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
        plan: AdaptiveCourseStructure,
    ) -> AdaptiveConceptBuildResult:
        """Persist adaptive concept metadata derived from a precomputed plan."""
        graph_service = ConceptGraphService(session)
        concept_graph = plan.ai_outline_meta.concept_graph

        layer_lookup = plan.layer_index()
        concepts_by_index: list[Concept] = []
        state_rows: list[dict[str, Any]] = []
        course_concept_rows: list[dict[str, Any]] = []

        for index, node in enumerate(concept_graph.nodes):
            layer_index = layer_lookup.get(index)
            difficulty = min(5, layer_index + 1) if layer_index is not None else None
            description = self._build_concept_description(node.title, plan.concept_tags_for_index(index))

            concept = await graph_service.create_concept(
                domain=course.title,
                name=node.title,
                description=description,
                slug=node.slug,
                difficulty=difficulty,
                generate_embedding=False,
            )
            concepts_by_index.append(concept)
            course_concept_rows.append(
                {
                    "course_id": course.id,
                    "concept_id": concept.id,
                    "order_hint": index,
                }
            )

            if node.initial_mastery is not None:
                state_rows.append(
                    {
                        "user_id": course.user_id,
                        "concept_id": concept.id,
                        "s_mastery": float(node.initial_mastery),
                    }
                )

        await self._insert_course_concepts(session=session, rows=course_concept_rows)

        await session.flush()

        seeded_state_count = await self._seed_owner_states(session=session, state_rows=state_rows)
        confusor_pair_count = await self._persist_confusors(
            session=session,
            concept_graph=concept_graph,
            concepts_by_index=concepts_by_index,
            course_id=course.id,
        )

        logger.info(
            "Adaptive concept seeding for course %s persisted %d user states and %d confusor pairs",
            course.id,
            seeded_state_count,
            confusor_pair_count,
        )

        node_count = len(concepts_by_index)
        edge_pairs: list[tuple[UUID, UUID]] = []
        for edge in concept_graph.edges:
            if edge.source_index >= node_count or edge.prereq_index >= node_count:
                logger.warning(
                    "Skipping edge due to out-of-range indices: %s depends on %s",
                    edge.source_index,
                    edge.prereq_index,
                )
                continue
            dependent = concepts_by_index[edge.source_index]
            prerequisite = concepts_by_index[edge.prereq_index]
            if dependent.id == prerequisite.id:
                continue
            edge_pairs.append((dependent.id, prerequisite.id))

        inserted_edges = await graph_service.add_prerequisites_bulk(edge_pairs)
        logger.info(
            "Adaptive concept graph inserted %d prerequisite edges for course %s",
            inserted_edges,
            course.id,
        )

        return AdaptiveConceptBuildResult(
            concepts_by_index=concepts_by_index,
        )
    async def _insert_course_concepts(
        self,
        *,
        session: AsyncSession,
        rows: list[dict[str, Any]],
    ) -> None:
        if not rows:
            return

        course_ids = [item["course_id"] for item in rows]
        concept_ids = [item["concept_id"] for item in rows]
        order_hints = [cast("int | None", item.get("order_hint")) for item in rows]

        stmt = text(
            """
            INSERT INTO course_concepts (course_id, concept_id, order_hint)
            SELECT *
            FROM UNNEST(
                :course_ids,
                :concept_ids,
                :order_hints
            )
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            bindparam("course_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("concept_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("order_hints", type_=ARRAY(Integer())),
        )

        await session.execute(
            stmt,
            {
                "course_ids": course_ids,
                "concept_ids": concept_ids,
                "order_hints": order_hints,
            },
        )

    async def _seed_owner_states(
        self,
        *,
        session: AsyncSession,
        state_rows: list[dict[str, Any]],
    ) -> int:
        if not state_rows:
            return 0

        user_ids = [item["user_id"] for item in state_rows]
        concept_ids = [item["concept_id"] for item in state_rows]
        mastery_scores = [float(item["s_mastery"]) for item in state_rows]

        state_stmt = text(
            """
            INSERT INTO user_concept_state (user_id, concept_id, s_mastery, exposures, learner_profile)
            SELECT u, c, s, 0, '{"success_rate": 0.5, "learning_speed": 1.0, "retention_rate": 0.8, "semantic_sensitivity": 1.0}'::jsonb
            FROM UNNEST(
                :user_ids,
                :concept_ids,
                :mastery_scores
            ) AS t(u, c, s)
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            bindparam("user_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("concept_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("mastery_scores", type_=ARRAY(Float())),
        )
        await session.execute(
            state_stmt,
            {
                "user_ids": user_ids,
                "concept_ids": concept_ids,
                "mastery_scores": mastery_scores,
            },
        )
        return len(state_rows)

    async def _persist_confusors(
        self,
        *,
        session: AsyncSession,
        concept_graph: Any,
        concepts_by_index: list[Concept],
        course_id: UUID,
    ) -> int:
        confusor_pairs: dict[tuple[UUID, UUID], float] = {}
        node_count = len(concepts_by_index)

        for confusor_set in concept_graph.confusors:
            base_index = int(confusor_set.index)
            if base_index < 0 or base_index >= node_count:
                logger.warning("Skipping confusor set due to out-of-range index: %s", confusor_set.index)
                continue

            base_concept = concepts_by_index[base_index]
            for confusor in confusor_set.confusors:
                other_index = int(confusor.index)
                if other_index < 0 or other_index >= node_count:
                    logger.warning("Skipping confusor pair due to out-of-range index: %s", confusor.index)
                    continue

                other_concept = concepts_by_index[other_index]
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
            # No pairs provided by the LLM; embedding-based confusors are computed post-creation
            # by ConceptGraphService.recompute_embedding_confusors_for_course().
            logger.debug("No LLM confusors provided for adaptive course %s", course_id)
            return 0

        now = datetime.now(UTC)
        concept_a_ids = [pair[0] for pair in confusor_pairs]
        concept_b_ids = [pair[1] for pair in confusor_pairs]
        similarities = [float(confusor_pairs[pair]) for pair in confusor_pairs]
        timestamps = [now for _ in confusor_pairs]

        stmt = text(
            """
            INSERT INTO concept_similarities (concept_a_id, concept_b_id, similarity, computed_at)
            SELECT *
            FROM UNNEST(
                :concept_a_ids,
                :concept_b_ids,
                :similarities,
                :timestamps
            )
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            bindparam("concept_a_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("concept_b_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("similarities", type_=ARRAY(Float())),
            bindparam("timestamps", type_=ARRAY(DateTime(timezone=True))),
        )
        await session.execute(
            stmt,
            {
                "concept_a_ids": concept_a_ids,
                "concept_b_ids": concept_b_ids,
                "similarities": similarities,
                "timestamps": timestamps,
            },
        )
        return len(confusor_pairs)
    def _build_adaptive_modules_payload(
        self,
        *,
        course: Course,
        plan: AdaptiveCourseStructure,
        concepts_by_index: list[Concept],
    ) -> list[dict[str, Any]]:
        """Return module payload (pre-normalization) derived from adaptive concepts."""
        lessons = self._build_adaptive_lessons_payload(
            course=course,
            plan=plan,
            concepts_by_index=concepts_by_index,
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
        plan: AdaptiveCourseStructure,
        concepts_by_index: list[Concept],
    ) -> list[dict[str, Any]]:
        """Build deterministic lesson payloads for adaptive concepts."""
        lessons: list[dict[str, Any]] = []
        assigned: set[int] = set()
        node_count = len(concepts_by_index)

        for order, lesson_plan in enumerate(plan.lessons):
            node_index = int(lesson_plan.index)
            if node_index < 0 or node_index >= node_count:
                logger.debug("Skipping adaptive lesson with out-of-range index %s for course %s", node_index, course.id)
                continue
            if node_index in assigned:
                logger.debug("Skipping duplicate adaptive lesson index %s for course %s", node_index, course.id)
                continue

            concept = concepts_by_index[node_index]
            lesson_id = uuid5(NAMESPACE_URL, f"concept-lesson:{course.id}:{concept.id}")
            lessons.append(
                {
                    "id": lesson_id,
                    "title": lesson_plan.title or concept.name,
                    "description": lesson_plan.description or concept.description,
                    "order": order,
                }
            )
            assigned.add(node_index)

        order_cursor = len(lessons)
        for node_index, concept in enumerate(concepts_by_index):
            if node_index in assigned:
                continue

            lesson_id = uuid5(NAMESPACE_URL, f"concept-lesson:{course.id}:{concept.id}")
            lessons.append(
                {
                    "id": lesson_id,
                    "title": concept.name,
                    "description": concept.description,
                    "order": order_cursor,
                }
            )
            order_cursor += 1

        return lessons
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

    def _build_modules_from_outline(self, lessons: list[Any]) -> list[dict[str, Any]]:
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
                    "description": None,
                    "lessons": [],
                }
                module_map[module_key] = module_entry
            lesson_slug = getattr(lesson, "slug", None)
            if lesson_slug is None and isinstance(lesson, dict):
                lesson_slug = lesson.get("slug")
            lessons_list = cast("list[dict[str, Any]]", module_entry.setdefault("lessons", []))
            if not isinstance(lessons_list, list):
                lessons_list = []
                module_entry["lessons"] = lessons_list
            lessons_list.append(
                {
                    "title": title,
                    "description": description,
                    "slug": lesson_slug,
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
        user_prompt: str | list[dict[str, Any]],
        prompt_text: str,
        user_id: UUID,
    ) -> dict[str, Any]:
        """Generate course data from AI prompt."""
        ai_result = await self.ai_service.generate_course_structure(
            user_id=user_id,
            user_prompt=user_prompt,
        )
        if not ai_result:
            error_msg = "Invalid AI response format for course generation"
            raise TypeError(error_msg)

        course_meta = getattr(ai_result, "course", None)
        if course_meta is None:
            error_msg = "AI generation returned no course metadata"
            raise RuntimeError(error_msg)

        title = course_meta.title
        description = course_meta.description or f"A course about {prompt_text}"

        modules = self._build_modules_from_outline(list(ai_result.lessons or []))
        if not modules:
            logger.warning("AI generated no lessons for prompt '%s'", prompt_text)

        result: dict[str, Any] = {
            "title": title,
            "description": description,
            "tags": [],
            "setup_commands": course_meta.setup_commands,
            "modules": modules,
        }

        return result
