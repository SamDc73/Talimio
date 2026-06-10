"""Pedagogical updater pass (sleep-time StudentCard consolidation).

Evidence writes nudge a cheap threshold trigger; a nightly sweep catches the
rest. The worker locks the learner-course watermark, computes deterministic
strategy aggregates in app code (the LLM never invents counts), extracts typed
facets from new critiques in one structured call, then lets the consolidation
model edit the StudentCard through text-editor tools. Facet writes, profile
updates, card edits, and the watermark advance commit in one transaction, so
retries after a crash are exactly-once.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from src.courses.models import LessonFeedbackEvent

from pydantic import BaseModel, Field, JsonValue
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget
from src.jobs import QUEUE_PEDAGOGY, defer_job, pedagogy_queueing_lock
from src.memory.notes_search import EMBEDDING_FAILURE_ERROR_TYPES
from src.memory.pedagogy_models import PedagogicalNote, PedagogyWatermark, StudentCard, TeachingEvent
from src.memory.pedagogy_service import TEACHING_PROFILE_FIELDS, upsert_course_teaching_profile
from src.memory.prompts import PEDAGOGY_UPDATER_SYSTEM_PROMPT
from src.memory.student_card import card_replace, card_rethink, lock_card


logger = logging.getLogger(__name__)

PEDAGOGY_UPDATER_TASK_NAME = "pedagogy.run_student_card_update"
EVIDENCE_TRIGGER_THRESHOLD = 10

_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_EVIDENCE_BATCH_LIMIT = 50
_NOTE_VERBATIM_QUOTE_MAX_CHARS = 300

_FACET_SIGNAL_FIELDS = (
    "pace_signal",
    "modality_signal",
    "example_style_signal",
    "quiz_density_signal",
    "tone_signal",
    "strategy_request_signal",
)


class FeedbackFacets(BaseModel):
    """Typed signals extracted from one lesson critique.

    All fields are required so weaker models cannot silently skip them;
    a signal the critique does not carry is an empty string.
    """

    event_index: int = Field(ge=0, description="Index of the critique in the payload's critiques list.")
    pace_signal: str = Field(description="Pacing signal, e.g. 'slower'; empty string when absent.")
    modality_signal: str = Field(description="Modality signal, e.g. 'more diagrams'; empty string when absent.")
    example_style_signal: str = Field(
        description="Example-style signal, e.g. 'worked examples first'; empty when absent."
    )
    quiz_density_signal: str = Field(description="Quiz-density signal, e.g. 'fewer quizzes'; empty string when absent.")
    tone_signal: str = Field(description="Tone signal, e.g. 'less chatty'; empty string when absent.")
    strategy_request_signal: str = Field(description="Requested teaching strategy; empty string when absent.")
    note: str = Field(
        description=(
            "Distilled retrieval-worthy pedagogical fact from this critique, 1-2 sentences; "
            "empty string when nothing is worth keeping long-term."
        )
    )
    scene_trace: str = Field(
        description=(
            "One line describing when/how the note was learned, with an absolute date "
            "(e.g. 'Critiqued the recursion lesson on 2026-06-10'); empty string when note is empty."
        )
    )


class TeachingProfileUpdate(BaseModel):
    """Inferred course-level preference updates; every field required, empty string = no change."""

    pace_preference: str
    example_style: str
    quiz_density_preference: str
    visual_preference: str
    video_preference: str
    tone_preference: str


class FacetExtraction(BaseModel):
    """Structured output schema for one batch of critiques."""

    facets: list[FeedbackFacets] = Field(default_factory=list)
    profile_update: TeachingProfileUpdate


_FACET_EXTRACTION_SYSTEM_PROMPT = """You extract typed pedagogical signals from raw lesson critiques on Talimio, a learning platform. You are a maintenance pass, not the assistant: never answer the learner, only classify their critiques.

Emit one facets entry per critique, keyed by its event_index from the payload. Every signal field is a short reusable phrase, e.g. pace_signal "slower", modality_signal "more diagrams", example_style_signal "worked examples first", quiz_density_signal "fewer quizzes", tone_signal "less chatty", strategy_request_signal "step-by-step derivations". Use the empty string when the critique carries no such signal; never guess.

Each facets entry also carries note and scene_trace. note is a distilled retrieval-worthy pedagogical fact (1-2 sentences) future lesson generation should be able to find, e.g. "Prefers labelled diagrams over prose when a concept has spatial structure." Use the empty string when the critique carries nothing worth keeping long-term — most routine critiques do not. scene_trace is one line saying when/how the note was learned with an absolute date from the critique's created_at, e.g. "Critiqued the recursion lesson on 2026-06-10"; empty string whenever note is empty.

Also emit profile_update: durable course-level teaching preferences this batch clearly supports (pace_preference, example_style, quiz_density_preference, visual_preference, video_preference, tone_preference). Each value is a short reusable phrase; use the empty string for no change. Only set a field the critiques state clearly and durably; an invented preference is the worst failure."""


async def defer_pedagogy_update(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> int | None:
    """Enqueue the updater for a learner-course pair inside the caller's transaction."""
    return await defer_job(
        session,
        task_name=PEDAGOGY_UPDATER_TASK_NAME,
        queue=QUEUE_PEDAGOGY,
        args={"user_id": str(user_id), "course_id": str(course_id)},
        queueing_lock=pedagogy_queueing_lock(user_id, course_id),
    )


async def maybe_trigger_update(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID, high_signal: bool = False
) -> bool:
    """Defer the updater once enough new evidence has accumulated past the watermark.

    ``high_signal`` evidence (the learner speaking in their own words: critiques,
    stated preferences) skips the threshold and consolidates immediately, so the
    very next lesson generation already knows. Passive evidence (quiz answers,
    completions) keeps the sleep-time economics.

    Two cheap index-backed counts, no lock: an off-by-one race only changes
    when the job is queued, and the queueing lock collapses duplicates anyway.
    """
    if high_signal:
        await defer_pedagogy_update(session, user_id=user_id, course_id=course_id)
        return True

    from src.courses.models import LessonFeedbackEvent

    last_processed_at = (
        await session.scalar(
            select(PedagogyWatermark.last_processed_at).where(
                PedagogyWatermark.user_id == user_id, PedagogyWatermark.course_id == course_id
            )
        )
        or _EPOCH
    )

    teaching_count = (
        await session.scalar(
            select(func.count())
            .select_from(TeachingEvent)
            .where(
                TeachingEvent.user_id == user_id,
                TeachingEvent.course_id == course_id,
                TeachingEvent.created_at > last_processed_at,
            )
        )
        or 0
    )
    feedback_count = (
        await session.scalar(
            select(func.count())
            .select_from(LessonFeedbackEvent)
            .where(LessonFeedbackEvent.course_id == course_id, LessonFeedbackEvent.created_at > last_processed_at)
        )
        or 0
    )

    if teaching_count + feedback_count < EVIDENCE_TRIGGER_THRESHOLD:
        return False
    await defer_pedagogy_update(session, user_id=user_id, course_id=course_id)
    return True


async def process_pedagogy_update(user_id: uuid.UUID, course_id: uuid.UUID) -> int:
    """Run one consolidation pass; returns how many new evidence items were processed."""
    from src.database.session import async_session_maker
    from src.memory.maintenance import _user_is_active

    async with async_session_maker() as session:
        if not await _user_is_active(session, user_id):
            return 0

        watermark = await _lock_watermark(session, user_id=user_id, course_id=course_id)
        new_events = await _load_new_teaching_events(
            session, user_id=user_id, course_id=course_id, after=watermark.last_processed_at
        )
        new_feedback = await _load_new_feedback_events(session, course_id=course_id, after=watermark.last_processed_at)
        if not new_events and not new_feedback:
            return 0

        all_events = list(
            await session.scalars(
                select(TeachingEvent)
                .where(TeachingEvent.user_id == user_id, TeachingEvent.course_id == course_id)
                .order_by(TeachingEvent.created_at)
            )
        )
        aggregates = compute_strategy_aggregates(all_events)

        pending_facets = [event for event in new_feedback if event.facets_extracted_at is None]
        if pending_facets:
            extraction = await _extract_facets(user_id=user_id, pending_events=pending_facets)
            await _apply_facet_extraction(
                session, course_id=course_id, pending_events=pending_facets, extraction=extraction
            )
            await _write_pedagogical_notes(
                session, user_id=user_id, course_id=course_id, pending_events=pending_facets, extraction=extraction
            )

        card = await lock_card(session, user_id=user_id, course_id=course_id)
        function_tools = _build_card_edit_tools(session, card)
        payload = _build_card_session_payload(
            card_text=card.card_text,
            aggregates=aggregates,
            new_events=new_events,
            new_feedback=new_feedback,
        )
        await _run_card_edit_session(user_id=user_id, payload=payload, function_tools=function_tools)

        watermark.last_processed_at = max(item.created_at for item in [*new_events, *new_feedback])
        await session.commit()
        return len(new_events) + len(new_feedback)


async def _lock_watermark(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> PedagogyWatermark:
    stmt = (
        select(PedagogyWatermark)
        .where(PedagogyWatermark.user_id == user_id, PedagogyWatermark.course_id == course_id)
        .with_for_update()
    )
    watermark = await session.scalar(stmt)
    if watermark is None:
        # Race-free get-or-create: a concurrent forget may be inserting the
        # same row; DO NOTHING + re-select FOR UPDATE blocks instead of erroring.
        await session.execute(
            text(
                "INSERT INTO pedagogy_watermarks (user_id, course_id) VALUES (:user_id, :course_id) "
                "ON CONFLICT (user_id, course_id) DO NOTHING"
            ),
            {"user_id": user_id, "course_id": course_id},
        )
        watermark = await session.scalar(stmt)
    if watermark is None:  # pragma: no cover - row guaranteed by the upsert
        msg = f"pedagogy watermark row missing for {user_id}/{course_id}"
        raise RuntimeError(msg)
    return watermark


async def _load_new_teaching_events(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID, after: datetime
) -> list[TeachingEvent]:
    stmt = (
        select(TeachingEvent)
        .where(
            TeachingEvent.user_id == user_id,
            TeachingEvent.course_id == course_id,
            TeachingEvent.created_at > after,
        )
        .order_by(TeachingEvent.created_at)
        .limit(_EVIDENCE_BATCH_LIMIT)
    )
    return list(await session.scalars(stmt))


async def _load_new_feedback_events(
    session: AsyncSession, *, course_id: uuid.UUID, after: datetime
) -> list[LessonFeedbackEvent]:
    from src.courses.models import LessonFeedbackEvent

    stmt = (
        select(LessonFeedbackEvent)
        .where(LessonFeedbackEvent.course_id == course_id, LessonFeedbackEvent.created_at > after)
        .order_by(LessonFeedbackEvent.created_at)
        .limit(_EVIDENCE_BATCH_LIMIT)
    )
    return list(await session.scalars(stmt))


def compute_strategy_aggregates(events: Sequence[TeachingEvent]) -> dict[str, JsonValue]:
    """Deterministic per-strategy counts handed to the LLM as ground truth."""
    grouped: dict[str, list[TeachingEvent]] = {}
    for event in events:
        grouped.setdefault(event.strategy_label or "unlabeled", []).append(event)

    strategies: dict[str, JsonValue] = {}
    for label, group in sorted(grouped.items()):
        durations = [event.duration_ms for event in group if event.duration_ms is not None]
        strategies[label] = {
            "events": len(group),
            "correct": sum(1 for event in group if event.outcome == "correct"),
            "incorrect": sum(1 for event in group if event.outcome == "incorrect"),
            "regenerations": sum(1 for event in group if event.event_type == "lesson_regenerated"),
            "avg_duration_ms": round(sum(durations) / len(durations)) if durations else None,
            "last_event_at": max(event.occurred_at for event in group).isoformat(),
        }

    return {
        "strategies": strategies,
        "totals": {
            "events": len(events),
            "correct": sum(1 for event in events if event.outcome == "correct"),
            "incorrect": sum(1 for event in events if event.outcome == "incorrect"),
            "regenerations": sum(1 for event in events if event.event_type == "lesson_regenerated"),
        },
    }


async def _extract_facets(*, user_id: uuid.UUID, pending_events: list[LessonFeedbackEvent]) -> FacetExtraction:
    """One structured call classifying every pending critique; the model only proposes."""
    from src.ai.client import LLMClient
    from src.config.settings import get_settings

    settings = get_settings()
    model = settings.MEMORY_LLM_MODEL.strip() or None

    payload: dict[str, object] = {
        "critiques": [
            {
                "event_index": index,
                "critique_text": event.critique_text,
                "apply_across_course": event.apply_across_course,
                "created_at": str(event.created_at),
            }
            for index, event in enumerate(pending_events)
        ],
    }

    client = LLMClient(agent_id="pedagogy-updater")
    result = await client.get_completion(
        [
            {"role": "system", "content": _FACET_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": _to_json(payload)},
        ],
        response_model=FacetExtraction,
        user_id=user_id,
        model=model,
        enable_memory=False,
        enable_tools=False,
    )
    if not isinstance(result, FacetExtraction):
        msg = "Expected FacetExtraction from facet structured output"
        raise TypeError(msg)
    return result


async def _apply_facet_extraction(
    session: AsyncSession,
    *,
    course_id: uuid.UUID,
    pending_events: list[LessonFeedbackEvent],
    extraction: FacetExtraction,
) -> None:
    """Write non-empty facets onto the event rows; apply inferred profile updates."""
    for facets in extraction.facets:
        if not 0 <= facets.event_index < len(pending_events):
            logger.info("pedagogy.updater.facet_index_out_of_range", extra={"event_index": facets.event_index})
            continue
        event = pending_events[facets.event_index]
        for name in _FACET_SIGNAL_FIELDS:
            value = getattr(facets, name).strip()
            if value:
                setattr(event, name, value)

    extracted_at = datetime.now(UTC)
    for event in pending_events:
        event.facets_extracted_at = extracted_at
    await session.flush()

    profile_fields = {
        name: getattr(extraction.profile_update, name).strip()
        for name in TEACHING_PROFILE_FIELDS
        if getattr(extraction.profile_update, name).strip()
    }
    if profile_fields:
        await upsert_course_teaching_profile(session, course_id=course_id, source="inferred", **profile_fields)


async def _write_pedagogical_notes(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    pending_events: list[LessonFeedbackEvent],
    extraction: FacetExtraction,
) -> None:
    """Insert one retrieval note per critique the extraction found worth keeping.

    Notes commit in the same transaction as the rest of the pass. Embeddings are
    computed inline but best-effort: a failed embedding stores the note with
    embedding NULL (the lexical leg still finds it) and never fails the job.
    """
    for facets in extraction.facets:
        note_text = facets.note.strip()
        if not note_text or not 0 <= facets.event_index < len(pending_events):
            continue
        event = pending_events[facets.event_index]
        session.add(
            PedagogicalNote(
                user_id=user_id,
                course_id=course_id,
                note=note_text,
                scene_trace=facets.scene_trace.strip(),
                verbatim_quote=event.critique_text[:_NOTE_VERBATIM_QUOTE_MAX_CHARS],
                source_kind="lesson_feedback_event",
                source_id=event.id,
                occurred_at=event.created_at,
                embedding=await _embed_note_text(note_text),
            )
        )
    await session.flush()


async def _embed_note_text(note_text: str) -> list[float] | None:
    """Embed one note inline; embedding failure must never fail the consolidation job."""
    from src.ai.rag.embeddings import VectorRAG
    from src.ai.rag.exceptions import RagUnavailableError

    try:
        return await VectorRAG().generate_embedding(note_text)
    except (RagUnavailableError, *EMBEDDING_FAILURE_ERROR_TYPES):
        logger.warning("pedagogy.updater.note_embedding_failed", exc_info=True)
        return None


STUDENT_CARD_REPLACE_TOOL_SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "student_card_replace",
        "description": (
            "Replace one exact snippet of the student card. old_str must match the current "
            "card text exactly once; include enough surrounding context to make it unique. "
            "Use for adding, updating, downgrading, or pruning individual claim lines."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "old_str": {"type": "string"},
                "new_str": {"type": "string"},
            },
            "required": ["old_str", "new_str"],
        },
    },
}

STUDENT_CARD_RETHINK_TOOL_SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "student_card_rethink",
        "description": (
            "Rewrite the whole student card as one consolidated block. All section "
            "headers must survive in their canonical order. Use when many claims need "
            "reorganizing at once, not for single-line edits."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {"new_text": {"type": "string"}},
            "required": ["new_text"],
        },
    },
}

STUDENT_CARD_FINISH_TOOL_SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "student_card_finish_edits",
        "description": "Signal that the card edit session is complete. Call exactly once, last.",
        "parameters": {"type": "object", "additionalProperties": False, "properties": {}},
    },
}


def _build_card_edit_tools(session: AsyncSession, card: StudentCard) -> list[FunctionToolDefinition]:
    """Text-editor tools closing over the locked card.

    CardEditError propagates out of the executors; the tool runtime formats it
    as an 'Error: ...' tool result the model can correct against next round.
    """

    async def execute_replace(arguments: Mapping[str, object]) -> str:
        await card_replace(
            session,
            card,
            old_str=str(arguments.get("old_str") or ""),
            new_str=str(arguments.get("new_str") or ""),
        )
        return f"ok, revision {card.revision}"

    async def execute_rethink(arguments: Mapping[str, object]) -> str:
        await card_rethink(session, card, new_text=str(arguments.get("new_text") or ""))
        return f"ok, revision {card.revision}"

    async def execute_finish(arguments: Mapping[str, object]) -> str:  # noqa: RUF029 - ToolExecutor protocol
        del arguments
        return "edits recorded"

    return [
        FunctionToolDefinition(
            schema=STUDENT_CARD_REPLACE_TOOL_SCHEMA, target=LocalToolTarget(execute=execute_replace)
        ),
        FunctionToolDefinition(
            schema=STUDENT_CARD_RETHINK_TOOL_SCHEMA, target=LocalToolTarget(execute=execute_rethink)
        ),
        FunctionToolDefinition(schema=STUDENT_CARD_FINISH_TOOL_SCHEMA, target=LocalToolTarget(execute=execute_finish)),
    ]


def _build_card_session_payload(
    *,
    card_text: str,
    aggregates: dict[str, JsonValue],
    new_events: list[TeachingEvent],
    new_feedback: list[LessonFeedbackEvent],
) -> dict[str, object]:
    return {
        "current_date": datetime.now(UTC).date().isoformat(),
        "student_card": card_text,
        "deterministic_aggregates": aggregates,
        "new_feedback_critiques": [
            {
                "created_at": str(event.created_at),
                "critique_text": event.critique_text,
                "apply_across_course": event.apply_across_course,
                "facets": {name: getattr(event, name) for name in _FACET_SIGNAL_FIELDS if getattr(event, name)},
            }
            for event in new_feedback
        ],
        "new_teaching_events": [
            {
                "occurred_at": str(event.occurred_at),
                "event_type": event.event_type,
                "strategy_label": event.strategy_label,
                "outcome": event.outcome,
                "duration_ms": event.duration_ms,
                "hints_used": event.hints_used,
                **({"details": event.details} if event.details else {}),
            }
            for event in new_events
        ],
    }


async def _run_card_edit_session(
    *,
    user_id: uuid.UUID,
    payload: dict[str, object],
    function_tools: list[FunctionToolDefinition],
) -> None:
    """One tool-loop completion; the client's autonomy loop executes the card edits."""
    from src.ai.client import LLMClient
    from src.config.settings import get_settings

    settings = get_settings()
    model = settings.MEMORY_LLM_MODEL.strip() or None

    client = LLMClient(agent_id="pedagogy-updater")
    await client.get_completion(
        [
            {"role": "system", "content": PEDAGOGY_UPDATER_SYSTEM_PROMPT},
            {"role": "user", "content": _to_json(payload)},
        ],
        function_tools=function_tools,
        user_id=user_id,
        model=model,
        enable_memory=False,
    )


_STALE_PAIRS_SQL = text(
    """
    SELECT evidence.user_id, evidence.course_id
    FROM (
        SELECT e.user_id, e.course_id, e.created_at
        FROM teaching_events e
        UNION ALL
        SELECT c.user_id, f.course_id, f.created_at
        FROM lesson_feedback_events f
        JOIN courses c ON c.id = f.course_id
    ) evidence
    LEFT JOIN pedagogy_watermarks w
        ON w.user_id = evidence.user_id AND w.course_id = evidence.course_id
    WHERE evidence.created_at > COALESCE(w.last_processed_at, 'epoch')
    GROUP BY evidence.user_id, evidence.course_id
    """
)


async def find_stale_pairs(session: AsyncSession) -> list[tuple[uuid.UUID, uuid.UUID]]:
    """All learner-course pairs with evidence newer than their watermark (or no watermark)."""
    result = await session.execute(_STALE_PAIRS_SQL)
    return [(row.user_id, row.course_id) for row in result]


def _to_json(payload: dict[str, object]) -> str:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str)
