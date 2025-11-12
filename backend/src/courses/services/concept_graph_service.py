"""Concept graph service providing DAG operations."""



import logging
import re
from collections.abc import Sequence
from typing import TypedDict
from uuid import UUID

from sqlalchemy import and_, bindparam, select, text, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.embeddings import VectorRAG
from src.config.settings import get_settings
from src.courses.models import Concept, ConceptPrerequisite, CourseConcept, UserConceptState


logger = logging.getLogger(__name__)


_SLUG_PATTERN = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    normalized = _SLUG_PATTERN.sub("-", value.lower()).strip("-")
    return normalized or "concept"


def _compose_embedding_text(name: str, description: str) -> str:
    normalized_name = (name or "").strip()
    normalized_description = (description or "").strip()
    if not normalized_description:
        return normalized_name
    if not normalized_name:
        return normalized_description
    return f"{normalized_name}\n\n{normalized_description}"


class FrontierEntry(TypedDict):
    """Typed structure representing a frontier concept entry."""

    concept: Concept
    state: UserConceptState | None
    prerequisites: list[UUID]
    unlocked: bool


class ConceptGraphService:
    """Service encapsulating concept graph CRUD operations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._vector = VectorRAG()
        settings = get_settings()
        self._unlock_threshold = float(getattr(settings, "ADAPTIVE_UNLOCK_MASTERY_THRESHOLD", 0.5))

    async def create_concept(
        self,
        *,
        domain: str,
        name: str,
        description: str,
        slug: str | None = None,
        difficulty: int | None = None,
        generate_embedding: bool = True,
    ) -> Concept:
        """Create a concept node with optional embedding generation."""
        slug_base = _slugify(slug or name)
        unique_slug = await self._ensure_unique_slug(slug_base)

        embedding: list[float] | None = None
        if generate_embedding:
            try:
                embedding_text = _compose_embedding_text(name, description)
                embedding = await self._vector.generate_embedding(embedding_text)
            except Exception:
                logger.warning("Failed to generate concept embedding for %s", name, exc_info=True)
        else:
            logger.debug("Deferring embedding generation for concept '%s'", name)

        concept = Concept(
            domain=domain,
            slug=unique_slug,
            name=name,
            description=description,
            difficulty=difficulty,
            embedding=embedding,
        )
        self._session.add(concept)
        await self._session.flush()

        logger.info("Created concept %s (%s)", concept.id, concept.slug)
        return concept

    async def add_prerequisite(self, *, concept_id: UUID, prereq_id: UUID) -> None:
        """Add prerequisite relation while preventing cycles."""
        if concept_id == prereq_id:
            msg = "A concept cannot depend on itself"
            raise ValueError(msg)

        await self._assert_no_cycle(concept_id=concept_id, prereq_id=prereq_id)

        link = ConceptPrerequisite(concept_id=concept_id, prereq_id=prereq_id)
        self._session.add(link)
        try:
            await self._session.flush()
        except IntegrityError as error:
            await self._session.rollback()
            logger.debug("Prerequisite already exists for concept %s -> %s", concept_id, prereq_id)
            msg = "Prerequisite already exists"
            raise ValueError(msg) from error

    async def add_prerequisites_bulk(self, edges: Sequence[tuple[UUID, UUID]]) -> int:
        """Insert prerequisite edges in bulk, ignoring duplicates."""
        unique_edges: list[dict[str, UUID]] = []
        seen: set[tuple[UUID, UUID]] = set()

        for concept_id, prereq_id in edges:
            if concept_id == prereq_id:
                continue
            pair = (concept_id, prereq_id)
            if pair in seen:
                continue
            seen.add(pair)
            unique_edges.append({"concept_id": concept_id, "prereq_id": prereq_id})

        if not unique_edges:
            return 0

        concept_ids = [entry["concept_id"] for entry in unique_edges]
        prereq_ids = [entry["prereq_id"] for entry in unique_edges]

        stmt = text(
            """
            INSERT INTO concept_prerequisites (concept_id, prereq_id)
            SELECT *
            FROM UNNEST(
                :concept_ids,
                :prereq_ids
            )
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            bindparam("concept_ids", type_=ARRAY(PGUUID(as_uuid=True))),
            bindparam("prereq_ids", type_=ARRAY(PGUUID(as_uuid=True))),
        )
        await self._session.execute(
            stmt,
            {
                "concept_ids": concept_ids,
                "prereq_ids": prereq_ids,
            },
        )
        return len(unique_edges)

    async def backfill_embeddings_for_course(self, course_id: UUID) -> int:
        """Generate embeddings for all concepts in a course that lack vectors."""
        result = await self._session.execute(
            select(Concept.id, Concept.name, Concept.description)
            .join(CourseConcept, CourseConcept.concept_id == Concept.id)
            .where(CourseConcept.course_id == course_id, Concept.embedding.is_(None))
            .order_by(Concept.created_at)
        )
        rows = result.all()
        concepts = [
            {
                "id": row.id,
                "name": row.name,
                "description": row.description,
            }
            for row in rows
        ]
        if not concepts:
            return 0

        batch_size = max(self._vector.batch_size, 1)
        total_updated = 0
        for start in range(0, len(concepts), batch_size):
            batch = concepts[start : start + batch_size]
            texts = [_compose_embedding_text(item["name"], item["description"]) for item in batch]
            embeddings = await self._vector.generate_embeddings(texts)
            for item, embedding in zip(batch, embeddings, strict=True):
                await self._session.execute(
                    update(Concept)
                    .where(Concept.id == item["id"])
                    .values(embedding=embedding)
                )
            total_updated += len(batch)

        await self._session.flush()
        logger.info(
            "Backfilled %s concept embeddings for course %s",
            total_updated,
            course_id,
        )
        return total_updated

    async def get_frontier(self, *, user_id: UUID, course_id: UUID) -> list[FrontierEntry]:
        """Return unlocked concepts for the learner."""
        concept_rows = await self._session.execute(
            select(Concept, UserConceptState)
            .select_from(CourseConcept)
            .join(Concept, CourseConcept.concept_id == Concept.id)
            .outerjoin(
                UserConceptState,
                and_(
                    UserConceptState.user_id == user_id,
                    UserConceptState.concept_id == CourseConcept.concept_id,
                ),
            )
            .where(CourseConcept.course_id == course_id)
        )
        records = concept_rows.all()
        if not records:
            return []

        concepts = [(row[0], row[1]) for row in records]
        concept_ids = [concept.id for concept, _ in concepts]
        prereq_rows = await self._session.execute(
            select(ConceptPrerequisite.concept_id, ConceptPrerequisite.prereq_id)
            .where(ConceptPrerequisite.concept_id.in_(concept_ids))
        )
        prereq_map: dict[UUID, set[UUID]] = {}
        for child_id, prereq_id in prereq_rows:
            prereq_map.setdefault(child_id, set()).add(prereq_id)

        state_lookup = {state.concept_id: state for _, state in concepts if state is not None}
        frontier: list[FrontierEntry] = []
        for concept, state in concepts:
            prereqs = prereq_map.get(concept.id, set())
            unlocked = True
            for prereq in prereqs:
                prereq_state = state_lookup.get(prereq)
                if prereq_state is None or (prereq_state.s_mastery is None) or (
                    float(prereq_state.s_mastery) < self._unlock_threshold
                ):
                    unlocked = False
                    break

            frontier.append(
                FrontierEntry(
                    concept=concept,
                    state=state,
                    prerequisites=list(prereqs),
                    unlocked=unlocked,
                )
            )

        return frontier

    async def get_concept_path(self, concept_id: UUID) -> Sequence[UUID]:
        """Return ordered prerequisite chain for a concept (nearest first)."""
        query = text(
            """
            WITH RECURSIVE prereqs AS (
                SELECT cp.prereq_id, cp.concept_id, 1 AS depth
                FROM concept_prerequisites cp
                WHERE cp.concept_id = :concept_id
                UNION ALL
                SELECT cp.prereq_id, cp.concept_id, prereqs.depth + 1
                FROM concept_prerequisites cp
                JOIN prereqs ON cp.concept_id = prereqs.prereq_id
            )
            SELECT prereq_id
            FROM prereqs
            ORDER BY depth
            """
        )
        result = await self._session.execute(query, {"concept_id": str(concept_id)})
        return [UUID(row[0]) for row in result]



    async def _ensure_unique_slug(self, base_slug: str) -> str:
        candidate = base_slug
        suffix = 1
        while True:
            exists = await self._session.scalar(select(Concept.id).where(Concept.slug == candidate))
            if not exists:
                return candidate
            suffix += 1
            candidate = f"{base_slug}-{suffix}"

    async def _assert_no_cycle(self, *, concept_id: UUID, prereq_id: UUID) -> None:
        """Ensure adding the edge does not introduce a cycle."""
        cycle_check = text(
            """
            WITH RECURSIVE ancestors AS (
                SELECT cp.concept_id, cp.prereq_id
                FROM concept_prerequisites cp
                WHERE cp.concept_id = :start_id
                UNION ALL
                SELECT cp.concept_id, cp.prereq_id
                FROM concept_prerequisites cp
                JOIN ancestors a ON cp.concept_id = a.prereq_id
            )
            SELECT 1 FROM ancestors WHERE prereq_id = :target_id LIMIT 1
            """
        )
        result = await self._session.execute(
            cycle_check,
            {"start_id": str(prereq_id), "target_id": str(concept_id)},
        )
        if result.scalar_one_or_none():
            msg = "Adding prerequisite would create a cycle"
            raise ValueError(msg)


