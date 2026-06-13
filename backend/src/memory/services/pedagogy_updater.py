"""Pedagogical updater pass (sleep-time StudentCard consolidation).

Evidence writes nudge a cheap threshold trigger; a nightly sweep catches the
rest. The worker computes deterministic strategy aggregates in app code (the
LLM never invents counts), extracts typed facets from new critiques in one
structured call, then lets the consolidation model plan StudentCard edits through
text-editor tools. Model calls run outside long-lived database locks; planned
card edits are written atomically with facets, notes, and the watermark.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from operator import itemgetter
from typing import TYPE_CHECKING, Literal, cast


if TYPE_CHECKING:
    from src.courses.models import LessonFeedbackEvent

from pydantic import BaseModel, Field, JsonValue  # noqa: TID251 - not an HTTP schema
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.prompts import PEDAGOGY_FACET_EXTRACTION_SYSTEM_PROMPT, PEDAGOGY_UPDATER_SYSTEM_PROMPT
from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget
from src.database.session import async_session_maker
from src.jobs import QUEUE_PEDAGOGY, defer_job, pedagogy_queueing_lock
from src.memory.models import PedagogicalNote, PedagogyWatermark, StudentCard, TeachingEvent
from src.memory.services.notes_search import EMBEDDING_FAILURE_ERROR_TYPES
from src.memory.services.pedagogy_service import TEACHING_PROFILE_FIELDS, upsert_course_teaching_profile
from src.memory.services.student_card import (
    card_replace,
    card_rethink,
    get_or_create_card,
    lock_card,
    preview_card_replace,
    preview_card_rethink,
)


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


@dataclass
class _PlannedCardEdit:
    tool: Literal["student_card_replace", "student_card_rethink"]
    arguments: dict[str, str]


async def defer_pedagogy_update(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> int | None:
    """Enqueue the updater for a learner-course pair inside the caller's transaction."""
    lock_key = pedagogy_queueing_lock(user_id, course_id)
    return await defer_job(
        session,
        task_name=PEDAGOGY_UPDATER_TASK_NAME,
        queue=QUEUE_PEDAGOGY,
        args={"user_id": str(user_id), "course_id": str(course_id)},
        queueing_lock=lock_key,
        lock=lock_key,
    )


async def maybe_trigger_update(session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID) -> bool:
    """Defer the updater once enough new measured evidence has accumulated past the watermark.

    Authored evidence never comes through here — its writer defers directly,
    in the same transaction. Two cheap index-backed counts, no lock: an
    off-by-one race only changes when the job is queued, and the queueing lock
    collapses duplicates anyway.
    """
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
    from src.memory.services.profile_maintenance import _user_is_active

    async with async_session_maker() as session:
        if not await _user_is_active(session, user_id):
            return 0

        new_events, new_feedback = await _load_evidence_batch(session, user_id=user_id, course_id=course_id)
        if not new_events and not new_feedback:
            return 0

        aggregates, card_text, card_revision = await _load_card_context(session, user_id=user_id, course_id=course_id)
        await session.commit()

    pending_facets = [event for event in new_feedback if event.facets_extracted_at is None]
    extraction, notes = await _prepare_facet_outputs(
        user_id=user_id,
        course_id=course_id,
        pending_facets=pending_facets,
    )

    function_tools, planned_card_edits = _build_card_edit_tools(
        initial_card_text=card_text,
        initial_revision=card_revision,
    )
    payload = _build_card_session_payload(
        card_text=card_text,
        aggregates=aggregates,
        new_events=new_events,
        new_feedback=new_feedback,
        pending_events=pending_facets,
        extraction=extraction,
    )
    await _run_card_edit_session(user_id=user_id, payload=payload, function_tools=function_tools)

    async with async_session_maker() as session:
        batch_max_created_at = max(item.created_at for item in [*new_events, *new_feedback])
        with session.no_autoflush:
            watermark = await _lock_watermark(session, user_id=user_id, course_id=course_id)
        if watermark.last_processed_at >= batch_max_created_at:
            await session.rollback()
            return 0

        if planned_card_edits:
            card = await lock_card(session, user_id=user_id, course_id=course_id)
            await _apply_card_edits(session, card=card, planned_edits=planned_card_edits)
        if extraction is not None:
            attached_pending_facets = await _load_feedback_events_by_id(
                session,
                [event.id for event in pending_facets],
            )
            if len(attached_pending_facets) != len(pending_facets):
                logger.info(
                    "pedagogy.updater.pending_feedback_changed",
                    extra={"course_id": str(course_id), "expected": len(pending_facets), "found": len(attached_pending_facets)},
                )
                await session.rollback()
                return 0
            await _apply_facet_extraction(
                session, course_id=course_id, pending_events=attached_pending_facets, extraction=extraction
            )
            await _write_pedagogical_notes(session, notes=notes)
        watermark.last_processed_at = max(watermark.last_processed_at, batch_max_created_at)
        await session.commit()
        return len(new_events) + len(new_feedback)


async def _load_evidence_batch(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> tuple[list[TeachingEvent], list[LessonFeedbackEvent]]:
    watermark = await _lock_watermark(session, user_id=user_id, course_id=course_id)
    teaching_candidates = await _load_new_teaching_events(
        session, user_id=user_id, course_id=course_id, after=watermark.last_processed_at
    )
    feedback_candidates = await _load_new_feedback_events(session, course_id=course_id, after=watermark.last_processed_at)
    return _select_oldest_evidence_batch(teaching_candidates, feedback_candidates)


async def _load_card_context(
    session: AsyncSession, *, user_id: uuid.UUID, course_id: uuid.UUID
) -> tuple[dict[str, JsonValue], str, int]:
    all_events = list(
        await session.scalars(
            select(TeachingEvent)
            .where(TeachingEvent.user_id == user_id, TeachingEvent.course_id == course_id)
            .order_by(TeachingEvent.created_at)
        )
    )
    card = await get_or_create_card(session, user_id=user_id, course_id=course_id)
    return compute_strategy_aggregates(all_events), card.card_text, card.revision


async def _prepare_facet_outputs(
    *, user_id: uuid.UUID, course_id: uuid.UUID, pending_facets: list[LessonFeedbackEvent]
) -> tuple[FacetExtraction | None, list[PedagogicalNote]]:
    if not pending_facets:
        return None, []
    extraction = await _extract_facets(user_id=user_id, pending_events=pending_facets)
    notes = await _build_pedagogical_notes(
        user_id=user_id, course_id=course_id, pending_events=pending_facets, extraction=extraction
    )
    return extraction, notes


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


async def _load_feedback_events_by_id(session: AsyncSession, event_ids: Sequence[uuid.UUID]) -> list[LessonFeedbackEvent]:
    from src.courses.models import LessonFeedbackEvent

    if not event_ids:
        return []

    events = await session.scalars(select(LessonFeedbackEvent).where(LessonFeedbackEvent.id.in_(event_ids)))
    by_id = {event.id: event for event in events}
    return [by_id[event_id] for event_id in event_ids if event_id in by_id]


def _select_oldest_evidence_batch(
    teaching_events: Sequence[TeachingEvent],
    feedback_events: Sequence[LessonFeedbackEvent],
) -> tuple[list[TeachingEvent], list[LessonFeedbackEvent]]:
    """Return one chronological batch across both evidence sources."""
    combined: list[tuple[datetime, str, TeachingEvent | LessonFeedbackEvent]] = [
        (event.created_at, "teaching", event) for event in teaching_events
    ]
    combined.extend((event.created_at, "feedback", event) for event in feedback_events)
    combined.sort(key=itemgetter(0))

    selected_events: list[TeachingEvent] = []
    selected_feedback: list[LessonFeedbackEvent] = []
    if len(combined) > _EVIDENCE_BATCH_LIMIT:
        cutoff_created_at = combined[_EVIDENCE_BATCH_LIMIT - 1][0]
        combined = [item for item in combined if item[0] <= cutoff_created_at]

    for _created_at, source, event in combined:
        if source == "teaching":
            selected_events.append(cast("TeachingEvent", event))
        else:
            selected_feedback.append(cast("LessonFeedbackEvent", event))
    return selected_events, selected_feedback


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
                "created_at": str(event.created_at),
            }
            for index, event in enumerate(pending_events)
        ],
    }

    client = LLMClient(agent_id="pedagogy-updater")
    result = await client.get_completion(
        [
            {"role": "system", "content": PEDAGOGY_FACET_EXTRACTION_SYSTEM_PROMPT},
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
    session.add_all(pending_events)
    _apply_facet_values(pending_events=pending_events, extraction=extraction)
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


def _apply_facet_values(*, pending_events: list[LessonFeedbackEvent], extraction: FacetExtraction) -> None:
    """Apply extracted facet values to in-memory feedback event objects."""
    for facets in extraction.facets:
        if not 0 <= facets.event_index < len(pending_events):
            logger.info("pedagogy.updater.facet_index_out_of_range", extra={"event_index": facets.event_index})
            continue
        event = pending_events[facets.event_index]
        for name in _FACET_SIGNAL_FIELDS:
            value = getattr(facets, name).strip()
            if value:
                setattr(event, name, value)


async def _build_pedagogical_notes(
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID,
    pending_events: list[LessonFeedbackEvent],
    extraction: FacetExtraction,
) -> list[PedagogicalNote]:
    """Build one retrieval note per critique the extraction found worth keeping.

    Embeddings are computed before the write transaction. A failed embedding
    stores the note with embedding NULL; the lexical leg still finds it.
    """
    notes: list[PedagogicalNote] = []
    for facets in extraction.facets:
        note_text = facets.note.strip()
        if not note_text or not 0 <= facets.event_index < len(pending_events):
            continue
        event = pending_events[facets.event_index]
        notes.append(
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
    return notes


async def _write_pedagogical_notes(session: AsyncSession, *, notes: list[PedagogicalNote]) -> None:
    """Insert prebuilt retrieval notes."""
    if not notes:
        return
    session.add_all(notes)
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


def _build_card_edit_tools(
    *,
    initial_card_text: str,
    initial_revision: int,
) -> tuple[list[FunctionToolDefinition], list[_PlannedCardEdit]]:
    """Text-editor tools that validate against an in-memory draft.

    CardEditError propagates out of the executors; the tool runtime formats it
    as an 'Error: ...' tool result the model can correct against next round.
    """
    draft_text = initial_card_text
    draft_revision = initial_revision
    planned_edits: list[_PlannedCardEdit] = []

    async def execute_replace(arguments: Mapping[str, object]) -> str:  # noqa: RUF029 - ToolExecutor protocol
        nonlocal draft_text, draft_revision
        old_str = str(arguments.get("old_str") or "")
        new_str = str(arguments.get("new_str") or "")
        draft_text = preview_card_replace(draft_text, old_str=old_str, new_str=new_str)
        draft_revision += 1
        planned_edits.append(
            _PlannedCardEdit(tool="student_card_replace", arguments={"old_str": old_str, "new_str": new_str})
        )
        return f"ok, revision {draft_revision}"

    async def execute_rethink(arguments: Mapping[str, object]) -> str:  # noqa: RUF029 - ToolExecutor protocol
        nonlocal draft_text, draft_revision
        new_text = str(arguments.get("new_text") or "")
        draft_text = preview_card_rethink(new_text=new_text)
        draft_revision += 1
        planned_edits.append(_PlannedCardEdit(tool="student_card_rethink", arguments={"new_text": new_text}))
        return f"ok, revision {draft_revision}"

    async def execute_finish(arguments: Mapping[str, object]) -> str:  # noqa: RUF029 - ToolExecutor protocol
        del arguments
        return "edits recorded"

    return [
        FunctionToolDefinition(schema=STUDENT_CARD_REPLACE_TOOL_SCHEMA, target=LocalToolTarget(execute=execute_replace)),
        FunctionToolDefinition(
            schema=STUDENT_CARD_RETHINK_TOOL_SCHEMA, target=LocalToolTarget(execute=execute_rethink)
        ),
        FunctionToolDefinition(schema=STUDENT_CARD_FINISH_TOOL_SCHEMA, target=LocalToolTarget(execute=execute_finish)),
    ], planned_edits


async def _apply_card_edits(
    session: AsyncSession, *, card: StudentCard, planned_edits: Sequence[_PlannedCardEdit]
) -> None:
    for edit in planned_edits:
        if edit.tool == "student_card_replace":
            await card_replace(
                session,
                card,
                old_str=edit.arguments["old_str"],
                new_str=edit.arguments["new_str"],
            )
            continue
        await card_rethink(session, card, new_text=edit.arguments["new_text"])


def _build_card_session_payload(
    *,
    card_text: str,
    aggregates: dict[str, JsonValue],
    new_events: list[TeachingEvent],
    new_feedback: list[LessonFeedbackEvent],
    pending_events: list[LessonFeedbackEvent],
    extraction: FacetExtraction | None,
) -> dict[str, object]:
    extracted_facets = _facet_payloads_by_event_id(pending_events=pending_events, extraction=extraction)
    return {
        "current_date": datetime.now(UTC).date().isoformat(),
        "student_card": card_text,
        "deterministic_aggregates": aggregates,
        "new_feedback_critiques": [
            {
                "created_at": str(event.created_at),
                "critique_text": event.critique_text,
                "facets": {
                    **{name: getattr(event, name) for name in _FACET_SIGNAL_FIELDS if getattr(event, name)},
                    **extracted_facets.get(event.id, {}),
                },
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


def _facet_payloads_by_event_id(
    *, pending_events: Sequence[LessonFeedbackEvent], extraction: FacetExtraction | None
) -> dict[uuid.UUID, dict[str, str]]:
    if extraction is None:
        return {}

    by_event_id: dict[uuid.UUID, dict[str, str]] = {}
    for facets in extraction.facets:
        if not 0 <= facets.event_index < len(pending_events):
            continue
        values = {name: getattr(facets, name).strip() for name in _FACET_SIGNAL_FIELDS if getattr(facets, name).strip()}
        if values:
            by_event_id[pending_events[facets.event_index].id] = values
    return by_event_id


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
