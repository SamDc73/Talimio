"""Simple assistant service with streaming support."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_ASSISTANT
from src.ai.client import LLMClient
from src.ai.errors import AIRuntimeError
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT
from src.exceptions import DomainError
from src.learning_capabilities.facade import LearningCapabilitiesFacade
from src.learning_capabilities.schemas import BuildContextBundleCapabilityInput

from . import conversations_service
from .schemas import ChatRequest


logger = logging.getLogger(__name__)

ASSISTANT_MAX_USER_MESSAGE_LENGTH = 8_000
ASSISTANT_MAX_HISTORY_MESSAGES = 40
ASSISTANT_REQUIRE_THREAD_ID = True
ASSISTANT_PUBLIC_ERROR_TEXT = "Sorry, I'm having trouble responding right now. Please try again."
RETRIEVAL_TRIGGER_THRESHOLD = 0.35
CONFUSION_TUTOR_TRIGGERS = (
    "i don't get",
    "i dont get",
    "i'm confused",
    "im confused",
    "confused",
    "i'm stuck",
    "im stuck",
    "stuck",
    "i don't understand",
    "i dont understand",
    "why is this wrong",
    "what did i do wrong",
    "wrong answer",
    "i got it wrong",
    "help me understand",
)
FOLLOW_UP_PROBE_TRIGGERS = (
    "check me",
    "check my",
    "quiz me",
    "test me",
    "practice",
    "try another",
    "again",
)


class NormalizedChatRequest(BaseModel):
    """Assistant request normalized from assistant-ui data stream payload."""

    latest_user_text: str = Field(default="")
    latest_user_blocks: list[dict[str, Any]] = Field(default_factory=list)
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    thread_id: uuid.UUID
    context_type: Literal["book", "video", "course"] | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, Any] | None = None

    model_config = ConfigDict(frozen=True)


def _sse_event(payload: dict[str, Any] | str) -> str:
    """Return a single SSE event line block."""
    encoded = payload if isinstance(payload, str) else json.dumps(payload)
    return f"data: {encoded}\n\n"


def _stream_chunk_to_sse_payload(chunk: Any) -> tuple[dict[str, Any] | None, str | None]:
    if not chunk:
        return None, None
    if isinstance(chunk, dict):
        return chunk, None
    delta = str(chunk)
    return {"type": "text-delta", "textDelta": delta}, delta


def _extract_message_text(content: Any) -> str:
    """Extract plain text from AI SDK-style message content parts."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text" and isinstance(part.get("text"), str):
            normalized = part["text"].strip()
            if normalized:
                text_parts.append(normalized)

    return " ".join(text_parts).replace("\n", " ").replace("\t", " ").strip()


def _is_image_file_part(media_type: Any, data_url: str) -> bool:
    if isinstance(media_type, str) and media_type.startswith("image/"):
        return True
    return data_url.startswith("data:image/")


def _convert_user_content_to_openai_blocks(content: Any) -> list[dict[str, Any]]:
    if isinstance(content, str):
        normalized = content.strip()
        if not normalized:
            return []
        return [{"type": "text", "text": normalized}]

    if not isinstance(content, list):
        return []

    blocks: list[dict[str, Any]] = []
    for part in content:
        if not isinstance(part, dict):
            continue

        part_type = part.get("type")
        if part_type == "text":
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                blocks.append({"type": "text", "text": text})
            continue

        if part_type == "file":
            data = part.get("data")
            if not isinstance(data, str) or not data.strip():
                continue

            media_type = part.get("mediaType")
            if not isinstance(media_type, str) or not media_type.strip():
                media_type = part.get("mimeType")

            if not _is_image_file_part(media_type, data):
                continue

            blocks.append({"type": "image_url", "image_url": {"url": data}})

    return blocks


def _normalize_chat_request(request: ChatRequest) -> NormalizedChatRequest:
    """Normalize assistant-ui runtime request body into assistant domain request."""
    if ASSISTANT_REQUIRE_THREAD_ID and request.thread_id is None:
        msg = "threadId is required"
        raise ValueError(msg)

    normalized_messages: list[dict[str, Any]] = []
    latest_user_blocks: list[dict[str, Any]] = []
    latest_user_text = ""
    last_user_index = -1

    for item in request.messages:
        if item.role not in {"user", "assistant"}:
            continue

        if item.role == "assistant":
            text = _extract_message_text(item.content)
            if not text:
                continue
            normalized_messages.append({"role": "assistant", "content": text})
            continue

        blocks = _convert_user_content_to_openai_blocks(item.content)
        if not blocks:
            continue

        latest_user_text = _extract_message_text(item.content)
        latest_user_blocks = blocks
        normalized_messages.append({"role": "user", "content": blocks})
        last_user_index = len(normalized_messages) - 1

    if last_user_index < 0 or not latest_user_blocks:
        msg = "Latest user message is required"
        raise ValueError(msg)

    if latest_user_text and len(latest_user_text) > ASSISTANT_MAX_USER_MESSAGE_LENGTH:
        msg = f"Latest user message exceeds max length of {ASSISTANT_MAX_USER_MESSAGE_LENGTH} characters"
        raise ValueError(msg)

    pending_quote = request.pending_quote.strip() if request.pending_quote else ""
    if pending_quote:
        latest_user_blocks = [{"type": "text", "text": f"{pending_quote}\n\n"}, *latest_user_blocks]
        latest_user_text = f"{pending_quote}\n\n{latest_user_text}" if latest_user_text else pending_quote

    history_start_index = max(last_user_index - ASSISTANT_MAX_HISTORY_MESSAGES, 0)

    return NormalizedChatRequest(
        latest_user_text=latest_user_text,
        latest_user_blocks=latest_user_blocks,
        conversation_history=normalized_messages[history_start_index:last_user_index],
        model=request.model_name or request.model,
        thread_id=request.thread_id,
        context_type=request.context_type,
        context_id=request.context_id,
        context_meta=_normalize_context_meta(request.context_meta),
    )


def _normalize_context_meta(context_meta: dict[str, Any] | None) -> dict[str, Any] | None:
    if context_meta is None:
        return None
    normalized = dict(context_meta)
    lesson_id = normalized.get("lesson_id") or normalized.get("lessonId")
    if lesson_id is not None:
        normalized["lesson_id"] = lesson_id
    return normalized


def _build_thread_message_payload(message: Any) -> dict[str, Any]:
    payload = message.model_dump(by_alias=True, exclude_none=True, mode="json")
    message_id = payload.get("id")
    if not isinstance(message_id, str) or not message_id.strip():
        payload["id"] = str(uuid.uuid4())
    created_at = payload.get("createdAt")
    if not isinstance(created_at, str) or not created_at.strip():
        payload["createdAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return payload


def _extract_latest_user_history_item(request: ChatRequest) -> dict[str, Any] | None:
    last_user_index = -1
    for index in range(len(request.messages) - 1, -1, -1):
        if request.messages[index].role == "user":
            last_user_index = index
            break
    if last_user_index < 0:
        return None

    return _attach_pending_quote_to_history_message(
        _build_thread_message_payload(request.messages[last_user_index]),
        request.pending_quote,
    )


def _attach_pending_quote_to_history_message(message: dict[str, Any], pending_quote: str | None) -> dict[str, Any]:
    quote = pending_quote.strip() if pending_quote else ""
    if not quote:
        return message

    quoted_message = dict(message)
    content = quoted_message.get("content")
    if isinstance(content, str):
        quoted_message["content"] = f"{quote}\n\n{content}"
    elif isinstance(content, list):
        quoted_message["content"] = [{"type": "text", "text": f"{quote}\n\n"}, *content]
    else:
        quoted_message["content"] = [{"type": "text", "text": quote}]
    return quoted_message


def _build_server_conversation_history(
    history_payload: dict[str, Any],
    *,
    exclude_message_id: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    history_items = history_payload.get("messages")
    if not isinstance(history_items, list):
        return messages

    for item in history_items:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, dict):
            continue
        if message.get("id") == exclude_message_id:
            continue

        role = message.get("role")
        if role == "assistant":
            text = _extract_message_text(message.get("content"))
            if text:
                messages.append({"role": "assistant", "content": text})
            continue

        if role == "user":
            blocks = _convert_user_content_to_openai_blocks(message.get("content"))
            if blocks:
                messages.append({"role": "user", "content": blocks})

    return messages[-ASSISTANT_MAX_HISTORY_MESSAGES:]


def _find_history_message_role(history_payload: dict[str, Any], message_id: str) -> str | None:
    history_items = history_payload.get("messages")
    if not isinstance(history_items, list):
        return None

    for item in history_items:
        if not isinstance(item, dict):
            continue
        message = item.get("message")
        if not isinstance(message, dict) or message.get("id") != message_id:
            continue
        role = message.get("role")
        return role if isinstance(role, str) else None
    return None


def _model_dump_jsonable(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(by_alias=True, exclude_none=True, mode="json")
        return dumped if isinstance(dumped, dict) else {}
    return {}


def _add_course_routing_state(packet: dict[str, Any], context_bundle: Any) -> None:
    if context_bundle.course_state is not None:
        course_state = _model_dump_jsonable(context_bundle.course_state)
        packet["courseState"] = {
            "courseId": course_state.get("courseId"),
            "title": course_state.get("title"),
            "adaptiveEnabled": course_state.get("adaptiveEnabled"),
            "completionPercentage": course_state.get("completionPercentage"),
            "totalLessons": course_state.get("totalLessons"),
            "currentLessonId": course_state.get("currentLessonId"),
        }

    if context_bundle.relevant_courses:
        packet["relevantCourses"] = [
            {
                "courseId": str(course.id),
                "title": course.title,
                "adaptiveEnabled": course.adaptive_enabled,
                "completionPercentage": course.completion_percentage,
            }
            for course in context_bundle.relevant_courses
        ]
    if context_bundle.course_catalog is not None:
        packet["courseCatalog"] = [
            {
                "courseId": str(course.course_id),
                "title": course.title,
                "adaptiveEnabled": course.adaptive_enabled,
            }
            for course in context_bundle.course_catalog
        ]
    if context_bundle.adaptive_catalog is not None:
        packet["adaptiveCatalog"] = [
            {
                "courseId": str(course.course_id),
                "title": course.title,
                "completionPercentage": course.completion_percentage,
                "currentLessonId": str(course.current_lesson_id) if course.current_lesson_id is not None else None,
                "currentLessonTitle": course.current_lesson_title,
                "dueCount": course.due_count,
                "avgMastery": course.avg_mastery,
            }
            for course in context_bundle.adaptive_catalog
        ]

    if context_bundle.course_outline is not None:
        outline = _model_dump_jsonable(context_bundle.course_outline)
        lessons = outline.get("lessons") or []
        packet["courseOutline"] = {
            "courseId": outline.get("courseId"),
            "lessonCount": len(lessons),
            "currentLessonIds": [lesson.get("lessonId") for lesson in lessons if lesson.get("isCurrent")],
            "lessonsWithContentCount": sum(1 for lesson in lessons if lesson.get("hasContent")),
        }


def _build_concept_routing_state(concept_focus: Any) -> dict[str, Any]:
    concept = _model_dump_jsonable(concept_focus)
    semantic_candidates = concept.get("semanticCandidates") or []
    top_candidate = semantic_candidates[0] if semantic_candidates else None
    top_match_score = top_candidate.get("matchScore") if isinstance(top_candidate, dict) else None
    weak_match = isinstance(top_match_score, (int, float)) and top_match_score < RETRIEVAL_TRIGGER_THRESHOLD
    concept_packet: dict[str, Any] = {
        "hasCurrentLessonConcept": concept.get("currentLessonConcept") is not None,
        "semanticCandidateCount": len(semantic_candidates),
        "topSemanticMatchScore": top_match_score,
        "weakSemanticMatch": weak_match,
    }
    current = concept.get("currentLessonConcept")
    if isinstance(current, dict):
        concept_packet["currentLessonConcept"] = {
            "conceptId": current.get("conceptId"),
            "name": current.get("name"),
            "lessonId": current.get("lessonId"),
            "lessonTitle": current.get("lessonTitle"),
            "mastery": current.get("mastery"),
            "exposures": current.get("exposures"),
            "due": current.get("due"),
            "confusorCount": len(current.get("confusors") or []),
            "prerequisiteGapCount": len(current.get("prerequisiteGaps") or []),
        }
    if isinstance(top_candidate, dict) and not weak_match:
        concept_packet["topSemanticCandidate"] = {
            "conceptId": top_candidate.get("conceptId"),
            "name": top_candidate.get("name"),
            "lessonId": top_candidate.get("lessonId"),
            "lessonTitle": top_candidate.get("lessonTitle"),
            "matchScore": top_candidate.get("matchScore"),
            "matchSource": top_candidate.get("matchSource"),
            "mastery": top_candidate.get("mastery"),
            "exposures": top_candidate.get("exposures"),
        }
    return concept_packet


def _add_focus_routing_state(packet: dict[str, Any], context_bundle: Any) -> None:
    if context_bundle.learner_profile is not None:
        packet["learnerProfile"] = _model_dump_jsonable(context_bundle.learner_profile)

    if context_bundle.lesson_focus is not None:
        lesson_focus = _model_dump_jsonable(context_bundle.lesson_focus)
        packet["lessonFocus"] = {
            "lessonId": lesson_focus.get("lessonId"),
            "title": lesson_focus.get("title"),
            "description": lesson_focus.get("description"),
            "hasLessonContent": bool(lesson_focus.get("hasContent")),
            "hasWindowPreview": bool(lesson_focus.get("windowPreview")),
        }
        packet["hasLessonContent"] = bool(lesson_focus.get("hasContent"))

    if context_bundle.concept_focus is not None:
        packet["conceptFocus"] = _build_concept_routing_state(context_bundle.concept_focus)


def _add_source_routing_state(packet: dict[str, Any], context_bundle: Any) -> None:
    if context_bundle.source_focus is None:
        return

    packet["sourceFocus"] = {
        "courseId": str(context_bundle.source_focus.course_id),
        "items": [
            {
                "title": item.title,
                "sourceType": item.source_type,
                "documentId": item.document_id,
                "chunkIndex": item.chunk_index,
                "totalChunks": item.total_chunks,
                "relevanceScore": item.similarity,
                "hasExcerpt": bool(item.excerpt.strip()),
            }
            for item in context_bundle.source_focus.items
        ],
    }


def _add_probe_routing_state(packet: dict[str, Any], context_bundle: Any) -> None:
    if context_bundle.active_probe_suggestion is not None:
        packet["activeProbeSuggestion"] = _model_dump_jsonable(context_bundle.active_probe_suggestion)
    if context_bundle.active_chat_probe is not None:
        active_probe = _model_dump_jsonable(context_bundle.active_chat_probe)
        packet["activeChatProbe"] = {
            "activeProbeId": active_probe.get("activeProbeId"),
            "courseId": active_probe.get("courseId"),
            "conceptId": active_probe.get("conceptId"),
            "lessonId": active_probe.get("lessonId"),
            "question": active_probe.get("question"),
            "answerKind": active_probe.get("answerKind"),
            "hints": active_probe.get("hints", []),
        }


def _add_frontier_routing_state(packet: dict[str, Any], context_bundle: Any) -> None:
    if context_bundle.frontier_state is None:
        return

    frontier = _model_dump_jsonable(context_bundle.frontier_state)
    packet["frontierState"] = {
        "dueCount": frontier.get("dueCount", 0),
        "avgMastery": frontier.get("avgMastery", 0.0),
        "dueForReview": _compact_frontier_items(frontier.get("dueForReview", [])),
        "frontier": _compact_frontier_items(frontier.get("frontier", [])),
        "comingSoon": _compact_frontier_items(frontier.get("comingSoon", [])),
    }


def _compact_frontier_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    compact_items = []
    for item in items[:3]:
        if not isinstance(item, dict):
            continue
        compact_items.append(
            {
                "conceptId": item.get("conceptId"),
                "name": item.get("name"),
                "mastery": item.get("mastery"),
                "exposures": item.get("exposures", 0),
                "nextReviewAt": item.get("nextReviewAt"),
            }
        )
    return compact_items


def _build_learning_routing_packet(context_bundle: Any) -> dict[str, Any]:
    """Return metadata for tool routing without embedding answer evidence."""
    packet: dict[str, Any] = {
        "contextType": context_bundle.context_type,
        "contextId": str(context_bundle.context_id) if context_bundle.context_id is not None else None,
        "courseMode": context_bundle.course_mode,
        "routingPolicy": {
            "retrievalTriggerThreshold": RETRIEVAL_TRIGGER_THRESHOLD,
            "answerEvidenceInjected": False,
        },
        "selectedQuotePresent": context_bundle.selected_quote is not None,
        "hasLessonContent": False,
        "hasSourceFocus": context_bundle.source_focus is not None and bool(context_bundle.source_focus.items),
        "hasFrontier": context_bundle.frontier_state is not None,
        "hasActiveProbe": context_bundle.active_chat_probe is not None,
    }

    _add_course_routing_state(packet, context_bundle)
    _add_focus_routing_state(packet, context_bundle)
    _add_source_routing_state(packet, context_bundle)
    _add_probe_routing_state(packet, context_bundle)
    _add_frontier_routing_state(packet, context_bundle)

    return {key: value for key, value in packet.items() if value is not None}


def _build_completion_metadata(
    *,
    request: NormalizedChatRequest,
    probe_submitted: bool,
    prefetched_learning_tools: list[str],
) -> dict[str, Any]:
    context_meta = request.context_meta or {}
    metadata: dict[str, Any] = {
        "assistant_thread_id": str(request.thread_id),
        "assistant_lesson_id": str(context_meta.get("lesson_id", "")),
        "assistant_probe_context": _build_probe_context(request),
    }
    if probe_submitted:
        metadata["probe_submitted"] = True
    if prefetched_learning_tools:
        metadata["prefetched_learning_tools"] = prefetched_learning_tools
    return metadata


def _latest_turn_needs_tutor_context(latest_user_text: str) -> bool:
    lowered = latest_user_text.lower()
    return any(trigger in lowered for trigger in CONFUSION_TUTOR_TRIGGERS)


def _current_concept_from_bundle(context_bundle: Any) -> Any | None:
    concept_focus = context_bundle.concept_focus
    if concept_focus is None:
        return None
    if concept_focus.current_lesson_concept is not None:
        return concept_focus.current_lesson_concept
    if concept_focus.semantic_candidates:
        return concept_focus.semantic_candidates[0]
    return None


def _tutor_context_target(context_bundle: Any, chat_probe_result: dict[str, Any] | None) -> tuple[str, str] | None:
    if chat_probe_result is not None:
        course_id = chat_probe_result.get("courseId")
        concept_id = chat_probe_result.get("conceptId")
        if isinstance(course_id, str) and isinstance(concept_id, str):
            return course_id, concept_id

    course_state = context_bundle.course_state
    course_id = str(course_state.course_id) if course_state is not None else None
    current_concept = _current_concept_from_bundle(context_bundle)
    if course_id is None or current_concept is None:
        return None
    return course_id, str(current_concept.concept_id)


def _context_signals_need_tutor_context(context_bundle: Any) -> bool:
    current_concept = _current_concept_from_bundle(context_bundle)
    if current_concept is None:
        return False
    if getattr(current_concept, "confusors", None):
        return True
    if getattr(current_concept, "prerequisite_gaps", None):
        return True
    active_suggestion = context_bundle.active_probe_suggestion
    return bool(active_suggestion is not None and active_suggestion.repeated_recent_misses)


def _submitted_probe_needs_tutor_context(chat_probe_result: dict[str, Any] | None) -> bool:
    if chat_probe_result is None:
        return False
    if chat_probe_result.get("reason") is not None:
        return False
    return chat_probe_result.get("isCorrect") is False


async def _maybe_get_tutor_context(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    request: NormalizedChatRequest,
    context_bundle: Any,
    chat_probe_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if context_bundle.course_mode != "adaptive":
        return None
    if _latest_turn_switches_topic(request.latest_user_text):
        return None
    if not (
        _latest_turn_needs_tutor_context(request.latest_user_text)
        or _submitted_probe_needs_tutor_context(chat_probe_result)
        or _context_signals_need_tutor_context(context_bundle)
    ):
        return None

    target = _tutor_context_target(context_bundle, chat_probe_result)
    if target is None:
        return None
    course_id, concept_id = target

    logger.info(
        "learning_capability.tutor_context.prefetch",
        extra={
            "user_id": str(user_id),
            "course_id": course_id,
            "concept_id": concept_id,
        },
    )
    return await learning_facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_concept_tutor_context",
        payload={
            "course_id": course_id,
            "concept_id": concept_id,
            "include_recent_probes": True,
            "include_lesson_summary": True,
        },
    )


async def _maybe_get_tutor_lesson_grounding(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    tutor_context: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if tutor_context is None:
        return None
    course_id = tutor_context.get("courseId")
    lesson_id = tutor_context.get("lessonId")
    if not isinstance(course_id, str) or not isinstance(lesson_id, str):
        return None

    return await learning_facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_lesson_windows",
        payload={
            "course_id": course_id,
            "lesson_id": lesson_id,
            "limit": 2,
        },
    )


def _latest_turn_asks_for_follow_up_probe(latest_user_text: str) -> bool:
    lowered = latest_user_text.lower()
    return any(trigger in lowered for trigger in FOLLOW_UP_PROBE_TRIGGERS)


def _latest_turn_asks_what_to_study(latest_user_text: str) -> bool:
    lowered = latest_user_text.lower()
    return any(trigger in lowered for trigger in ("what should i study", "what to study", "what is due", "what's due"))


def _generated_probe_is_ready(result: dict[str, Any]) -> bool:
    return result.get("activeProbeId") is not None and isinstance(result.get("probe"), dict)


def _latest_turn_switches_topic(latest_user_text: str) -> bool:
    lowered = latest_user_text.lower()
    explicit_switches = ("switch topic", "switch topics", "change topic", "new topic", "instead")
    practice_switches = ("quiz me on", "test me on", "practice", "review")
    topic_starters = ("let's do", "lets do", "can we do", "i want to do")
    return (
        any(trigger in lowered for trigger in explicit_switches)
        or any(trigger in lowered and (" on " in lowered or " instead" in lowered) for trigger in practice_switches)
        or lowered.startswith(topic_starters)
    )


def _course_id_from_context_bundle(context_bundle: Any) -> str | None:
    course_state = context_bundle.course_state
    return str(course_state.course_id) if course_state is not None else None


async def _maybe_get_requested_course_frontier(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    request: NormalizedChatRequest,
    context_bundle: Any,
) -> dict[str, Any] | None:
    if context_bundle.course_mode != "adaptive" or not _latest_turn_asks_what_to_study(request.latest_user_text):
        return None
    course_id = _course_id_from_context_bundle(context_bundle)
    if course_id is None:
        return None

    logger.info(
        "learning_capability.study_next.get_course_frontier",
        extra={"user_id": str(user_id), "course_id": course_id},
    )
    return await learning_facade.execute_read_capability(
        user_id=user_id,
        capability_name="get_course_frontier",
        payload={"course_id": course_id},
    )


async def _maybe_search_switched_topic(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    request: NormalizedChatRequest,
    context_bundle: Any,
) -> dict[str, Any] | None:
    if context_bundle.course_mode != "adaptive" or not _latest_turn_switches_topic(request.latest_user_text):
        return None
    course_id = _course_id_from_context_bundle(context_bundle)
    if course_id is None:
        return None

    logger.info(
        "learning_capability.topic_switch.search_concepts",
        extra={"user_id": str(user_id), "course_id": course_id},
    )
    return await learning_facade.execute_read_capability(
        user_id=user_id,
        capability_name="search_concepts",
        payload={
            "course_id": course_id,
            "query": request.latest_user_text,
            "limit": 5,
            "include_state": True,
        },
    )


async def _maybe_generate_topic_switch_probe(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    request: NormalizedChatRequest,
    topic_switch_concepts: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if (
        topic_switch_concepts is None
        or not _latest_turn_asks_for_follow_up_probe(request.latest_user_text)
    ):
        return None

    items = topic_switch_concepts.get("items")
    if not isinstance(items, list) or not items:
        return None
    first_item = items[0]
    if not isinstance(first_item, dict):
        return None
    course_id = topic_switch_concepts.get("courseId")
    concept_id = first_item.get("conceptId")
    if not isinstance(course_id, str) or not isinstance(concept_id, str):
        return None

    payload: dict[str, Any] = {
        "course_id": course_id,
        "concept_id": concept_id,
        "count": 1,
        "practice_context": "chat",
        "learner_context": request.latest_user_text[:2000],
        "thread_id": str(request.thread_id),
    }
    lesson_id = first_item.get("lessonId")
    if isinstance(lesson_id, str):
        payload["lesson_id"] = lesson_id
    try:
        result = await learning_facade.execute_action_capability(
            user_id=user_id,
            capability_name="generate_concept_probe",
            payload=payload,
        )
        return result if _generated_probe_is_ready(result) else None
    except DomainError as error:
        logger.warning(
            "learning_capability.topic_switch_probe.skipped",
            extra={"user_id": str(user_id), "course_id": course_id, "concept_id": concept_id, "reason": str(error)},
        )
        return None


async def _maybe_generate_tutor_follow_up_probe(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    request: NormalizedChatRequest,
    context_bundle: Any,
    tutor_context: dict[str, Any] | None,
    chat_probe_result: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if tutor_context is None or context_bundle.active_chat_probe is not None:
        return None
    if _latest_turn_switches_topic(request.latest_user_text):
        return None
    if not (
        _latest_turn_asks_for_follow_up_probe(request.latest_user_text)
        or _submitted_probe_needs_tutor_context(chat_probe_result)
    ):
        return None

    course_id = tutor_context.get("courseId")
    concept_id = tutor_context.get("conceptId")
    lesson_id = tutor_context.get("lessonId")
    if not isinstance(course_id, str) or not isinstance(concept_id, str):
        return None

    logger.info(
        "learning_capability.tutor_follow_up_probe.generate",
        extra={
            "user_id": str(user_id),
            "course_id": course_id,
            "concept_id": concept_id,
        },
    )
    payload: dict[str, Any] = {
        "course_id": course_id,
        "concept_id": concept_id,
        "count": 1,
        "practice_context": "chat",
        "learner_context": request.latest_user_text[:2000],
        "thread_id": str(request.thread_id),
    }
    if isinstance(lesson_id, str):
        payload["lesson_id"] = lesson_id
    try:
        result = await learning_facade.execute_action_capability(
            user_id=user_id,
            capability_name="generate_concept_probe",
            payload=payload,
        )
        return result if _generated_probe_is_ready(result) else None
    except DomainError as error:
        logger.warning(
            "learning_capability.tutor_follow_up_probe.skipped",
            extra={
                "user_id": str(user_id),
                "course_id": course_id,
                "concept_id": concept_id,
                "reason": str(error),
            },
        )
        return None


async def _persist_completed_assistant_message(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: str,
    parent_id: str,
    text: str,
    run_config: dict[str, Any] | None,
) -> None:
    normalized_text = text.strip()
    if not normalized_text:
        return

    assistant_message = {
        "id": message_id,
        "role": "assistant",
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "content": [{"type": "text", "text": normalized_text}],
    }
    await conversations_service.append_assistant_conversation_history_item(
        session=session,
        user_id=user_id,
        conversation_id=conversation_id,
        message=assistant_message,
        parent_id=parent_id,
        run_config=run_config,
    )


async def _persist_incomplete_assistant_message(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: str,
    parent_id: str,
    run_config: dict[str, Any] | None,
) -> None:
    incomplete_message = {
        "id": message_id,
        "role": "assistant",
        "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "content": [],
        "status": {"type": "incomplete", "reason": "error"},
    }
    await conversations_service.append_assistant_conversation_history_item(
        session=session,
        user_id=user_id,
        conversation_id=conversation_id,
        message=incomplete_message,
        parent_id=parent_id,
        run_config=run_config,
    )
    await session.commit()


async def _stream_completion_and_persist_history(
    *,
    stream: AsyncGenerator[Any],
    session: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message_id: str,
    parent_id: str,
    run_config: dict[str, Any] | None,
) -> AsyncGenerator[str]:
    assistant_text_parts: list[str] = []
    saw_any_content = False

    async for chunk in stream:
        payload, delta = _stream_chunk_to_sse_payload(chunk)
        if payload is None:
            continue
        saw_any_content = saw_any_content or delta is not None
        if delta is not None:
            assistant_text_parts.append(delta)
        yield _sse_event(payload)

    if not saw_any_content:
        logger.warning("Assistant returned empty streamed response for user %s", user_id)
        fallback_content = "I couldn't retrieve results right now. Please try again."
        assistant_text_parts.append(fallback_content)
        yield _sse_event({"type": "text-delta", "textDelta": fallback_content})

    await _persist_completed_assistant_message(
        session=session,
        user_id=user_id,
        conversation_id=conversation_id,
        message_id=message_id,
        parent_id=parent_id,
        text="".join(assistant_text_parts),
        run_config=run_config,
    )
    await session.commit()

    yield _sse_event(
        {
            "type": "finish",
            "finishReason": "stop",
            "usage": {"promptTokens": 0, "completionTokens": 0},
        }
    )
    yield _sse_event("[DONE]")


async def _persist_latest_user_and_load_server_history(
    *,
    session: AsyncSession,
    user_id: uuid.UUID,
    request: ChatRequest,
    normalized_request: NormalizedChatRequest,
) -> tuple[NormalizedChatRequest, str]:
    existing_history = await conversations_service.load_assistant_conversation_history(
        session=session,
        user_id=user_id,
        conversation_id=normalized_request.thread_id,
        lock_for_update=True,
    )
    latest_user_message = _extract_latest_user_history_item(request)
    if latest_user_message is None:
        msg = "Latest user message is required"
        raise ValueError(msg)

    raw_user_message_id = latest_user_message.get("id")
    if not isinstance(raw_user_message_id, str) or not raw_user_message_id.strip():
        msg = "Latest user message id is required"
        raise ValueError(msg)

    head_id = existing_history.get("head_id")
    if isinstance(head_id, str) and head_id != raw_user_message_id:
        head_role = _find_history_message_role(existing_history, head_id)
        if head_role == "user":
            msg = "Previous user message is still awaiting assistant response"
            raise ValueError(msg)

    latest_user_parent_id = head_id if isinstance(head_id, str) and head_id.strip() else None
    inserted = await conversations_service.append_assistant_conversation_history_item(
        session=session,
        user_id=user_id,
        conversation_id=normalized_request.thread_id,
        message=latest_user_message,
        parent_id=latest_user_parent_id,
        run_config=request.run_config,
    )
    if inserted:
        await session.commit()
    else:
        msg = "Latest user message already exists"
        raise ValueError(msg)

    persisted_history = await conversations_service.load_assistant_conversation_history(
        session=session,
        user_id=user_id,
        conversation_id=normalized_request.thread_id,
    )
    request_with_server_history = normalized_request.model_copy(
        update={
            "conversation_history": _build_server_conversation_history(
                persisted_history,
                exclude_message_id=raw_user_message_id,
            )
        }
    )
    return request_with_server_history, raw_user_message_id


async def assistant_chat(
    request: ChatRequest,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> AsyncGenerator[str]:
    """Stream chat responses with optional context using ui-message-stream protocol."""
    message_id = str(uuid.uuid4())
    normalized_request: NormalizedChatRequest | None = None
    latest_user_message_id: str | None = None
    try:
        # Emit start immediately so the client can render streaming state while prep runs.
        yield _sse_event({"type": "start", "messageId": message_id})

        normalized_request = _normalize_chat_request(request)
        normalized_request, latest_user_message_id = await _persist_latest_user_and_load_server_history(
            session=session,
            user_id=user_id,
            request=request,
            normalized_request=normalized_request,
        )

        # Build messages with context if available
        messages, probe_submitted, prefetched_learning_tools = await _build_messages(normalized_request, user_id, session)

        # Run completion through shared LLM client so memories and MCP tools are available
        llm_client = LLMClient(agent_id=AGENT_ID_ASSISTANT)
        metadata = _build_completion_metadata(
            request=normalized_request,
            probe_submitted=probe_submitted,
            prefetched_learning_tools=prefetched_learning_tools,
        )
        stream = await llm_client.get_completion(
            messages=messages,
            user_id=user_id,
            model=normalized_request.model,
            stream=True,
            metadata=metadata,
        )

        async for event in _stream_completion_and_persist_history(
            stream=stream,
            session=session,
            user_id=user_id,
            conversation_id=normalized_request.thread_id,
            message_id=message_id,
            parent_id=latest_user_message_id,
            run_config=request.run_config,
        ):
            yield event

    except asyncio.CancelledError:
        if normalized_request and latest_user_message_id:
            try:
                await session.rollback()
                await _persist_incomplete_assistant_message(
                    session=session,
                    user_id=user_id,
                    conversation_id=normalized_request.thread_id,
                    message_id=message_id,
                    parent_id=latest_user_message_id,
                    run_config=request.run_config,
                )
            except (RuntimeError, TypeError, ValueError, OSError, SQLAlchemyError, DomainError):
                logger.exception(
                    "Failed to persist cancelled assistant message for thread %s",
                    normalized_request.thread_id,
                )
        raise
    except (ValueError, DomainError) as error:
        logger.warning("Chat validation failed for user %s: %s", user_id, error)
        yield _sse_event({"type": "error", "errorText": ASSISTANT_PUBLIC_ERROR_TEXT})
        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "error",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")
    except (AIRuntimeError, RuntimeError, TypeError, OSError, SQLAlchemyError) as error:
        if isinstance(error, AIRuntimeError):
            logger.warning(
                "LLM runtime failure for user %s: %s (%s)",
                user_id,
                error,
                error.category.value,
            )
        else:
            logger.exception("Chat failed for user %s", user_id)
        if normalized_request and latest_user_message_id:
            try:
                if isinstance(error, SQLAlchemyError):
                    await session.rollback()
                await _persist_incomplete_assistant_message(
                    session=session,
                    user_id=user_id,
                    conversation_id=normalized_request.thread_id,
                    message_id=message_id,
                    parent_id=latest_user_message_id,
                    run_config=request.run_config,
                )
            except (RuntimeError, TypeError, ValueError, OSError, SQLAlchemyError, DomainError):
                logger.exception(
                    "Failed to persist incomplete assistant message for thread %s",
                    normalized_request.thread_id,
                )
        yield _sse_event({"type": "error", "errorText": ASSISTANT_PUBLIC_ERROR_TEXT})
        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "error",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")


def _append_prefetched_learning_blocks(
    *,
    user_blocks: list[dict[str, Any]],
    requested_frontier: dict[str, Any] | None,
    topic_switch_concepts: dict[str, Any] | None,
    topic_switch_probe: dict[str, Any] | None,
) -> None:
    if requested_frontier is not None:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[requested_course_frontier]\n{json.dumps(requested_frontier, default=str)}",
            }
        )
    if topic_switch_concepts is not None:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[topic_switch_concept_search]\n{json.dumps(topic_switch_concepts, default=str)}",
            }
        )
    if topic_switch_probe is not None:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[topic_switch_probe]\n{json.dumps(topic_switch_probe, default=str)}",
            }
        )
        user_blocks.append(
            {
                "type": "text",
                "text": "\n\n[topic_switch_probe_contract]\nShow this generated probe without raw ids. Keep activeProbeId hidden for tool calls only. Do not call `generate_concept_probe` again for this turn.",
            }
        )


async def _build_messages(
    request: NormalizedChatRequest,
    user_id: uuid.UUID,
    session: AsyncSession,
) -> tuple[list[dict[str, Any]], bool, list[str]]:
    """Build message list with capability-backed context packet injection."""
    learning_facade = LearningCapabilitiesFacade(session)
    context_meta = dict(request.context_meta or {})
    context_meta["thread_id"] = str(request.thread_id)
    context_bundle = await learning_facade.build_context_bundle(
        user_id=user_id,
        payload=BuildContextBundleCapabilityInput(
            context_type=request.context_type,
            context_id=request.context_id,
            context_meta=context_meta,
            latest_user_text=request.latest_user_text,
            selected_quote=None,
        ),
    )
    logger.info(
        "learning_capability.context_bundle.injected",
        extra={
            "user_id": str(user_id),
            "context_type": context_bundle.context_type,
            "has_course_state": context_bundle.course_state is not None,
            "has_lesson_state": context_bundle.lesson_state is not None,
            "has_frontier_state": context_bundle.frontier_state is not None,
            "relevant_course_count": len(context_bundle.relevant_courses),
        },
    )

    chat_probe_result = await _maybe_submit_active_chat_probe(
        learning_facade=learning_facade,
        user_id=user_id,
        request=request,
        context_bundle=context_bundle,
        session=session,
    )
    probe_submitted = chat_probe_result is not None
    requested_frontier = await _maybe_get_requested_course_frontier(
        learning_facade=learning_facade,
        user_id=user_id,
        request=request,
        context_bundle=context_bundle,
    )
    topic_switch_concepts = await _maybe_search_switched_topic(
        learning_facade=learning_facade,
        user_id=user_id,
        request=request,
        context_bundle=context_bundle,
    )
    topic_switch_probe = await _maybe_generate_topic_switch_probe(
        learning_facade=learning_facade,
        user_id=user_id,
        request=request,
        topic_switch_concepts=topic_switch_concepts,
    )
    tutor_context = await _maybe_get_tutor_context(
        learning_facade=learning_facade,
        user_id=user_id,
        request=request,
        context_bundle=context_bundle,
        chat_probe_result=chat_probe_result,
    )
    tutor_lesson_grounding = await _maybe_get_tutor_lesson_grounding(
        learning_facade=learning_facade,
        user_id=user_id,
        tutor_context=tutor_context,
    )
    follow_up_probe = await _maybe_generate_tutor_follow_up_probe(
        learning_facade=learning_facade,
        user_id=user_id,
        request=request,
        context_bundle=context_bundle,
        tutor_context=tutor_context,
        chat_probe_result=chat_probe_result,
    )
    if topic_switch_probe is not None or follow_up_probe is not None:
        await session.commit()
    prefetched_learning_tools: list[str] = []
    if requested_frontier is not None:
        prefetched_learning_tools.append("get_course_frontier")
    if topic_switch_concepts is not None:
        prefetched_learning_tools.append("search_concepts")
    if topic_switch_probe is not None:
        prefetched_learning_tools.append("generate_concept_probe")
    if tutor_context is not None:
        prefetched_learning_tools.append("get_concept_tutor_context")
    if follow_up_probe is not None:
        prefetched_learning_tools.append("generate_concept_probe")

    messages: list[dict[str, Any]] = [{"role": "system", "content": ASSISTANT_CHAT_SYSTEM_PROMPT}]
    messages.extend(request.conversation_history)

    user_blocks = list(request.latest_user_blocks)
    context_packet = _build_learning_routing_packet(context_bundle)
    user_blocks.append({"type": "text", "text": f"\n\n[learning_context_packet]\n{json.dumps(context_packet, default=str)}"})
    _append_prefetched_learning_blocks(
        user_blocks=user_blocks,
        requested_frontier=requested_frontier,
        topic_switch_concepts=topic_switch_concepts,
        topic_switch_probe=topic_switch_probe,
    )
    if probe_submitted:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[chat_probe_submission_result]\n{json.dumps(chat_probe_result, default=str)}",
            }
        )
    if tutor_context is not None:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[concept_tutor_context]\n{json.dumps(tutor_context, default=str)}",
            }
        )
        user_blocks.append(
            {
                "type": "text",
                "text": (
                    "\n\n[tutor_response_contract]\n"
                    "Use the tutor context as possible evidence, not a diagnosis. "
                    "Identify the smallest likely false belief non-shamingly, repair it using course terms, "
                    "then offer one short follow-up probe for the same concept."
                ),
            }
        )
    if tutor_lesson_grounding is not None:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[tutor_lesson_grounding]\n{json.dumps(tutor_lesson_grounding, default=str)}",
            }
        )
    if follow_up_probe is not None:
        user_blocks.append(
            {
                "type": "text",
                "text": f"\n\n[tutor_follow_up_probe]\n{json.dumps(follow_up_probe, default=str)}",
            }
        )
        user_blocks.append(
            {
                "type": "text",
                "text": (
                    "\n\n[follow_up_probe_contract]\n"
                    "Show this generated probe without raw ids. Keep activeProbeId hidden for tool calls only. Do not write an ad-hoc replacement question."
                ),
            }
        )

    messages.append({"role": "user", "content": user_blocks})
    return messages, probe_submitted, prefetched_learning_tools


async def _maybe_submit_active_chat_probe(
    *,
    learning_facade: LearningCapabilitiesFacade,
    user_id: uuid.UUID,
    request: NormalizedChatRequest,
    context_bundle: Any,
    session: AsyncSession,
) -> dict[str, Any] | None:
    active_probe = context_bundle.active_chat_probe
    learner_answer = _extract_chat_probe_answer(request.latest_user_text)
    if active_probe is None or learner_answer is None:
        return None

    result = await learning_facade.execute_action_capability(
        user_id=user_id,
        capability_name="submit_concept_probe_result",
        payload={
            "course_id": str(active_probe.course_id),
            "active_probe_id": str(active_probe.active_probe_id),
            "learner_answer": learner_answer,
            "thread_id": str(request.thread_id),
            "lesson_id": str(active_probe.lesson_id),
        },
    )
    await session.commit()
    if result.get("reason") is None:
        context_bundle.active_chat_probe = None
    return result


def _extract_chat_probe_answer(latest_user_text: str) -> str | None:
    text = latest_user_text.strip()
    lowered = text.lower()
    if not text or _latest_turn_switches_topic(lowered):
        return None
    help_question_starters = ("can you", "could you", "what", "why", "how", "explain", "help", "give me", "show me")
    explicit_submission_markers = ("submit my answer", "please grade", "please record")
    if lowered.startswith(help_question_starters) and not any(marker in lowered for marker in explicit_submission_markers):
        return None
    strong_answer_markers = (
        "my answer is",
        "the answer is",
        "answer is",
        "here is my answer",
        "submit my answer",
        "please grade",
        "please record",
    )
    if any(marker in lowered for marker in strong_answer_markers):
        return text
    has_answer_shape = any(character.isdigit() for character in text) or lowered in {"a", "b", "c", "d", "true", "false"}
    weak_answer_markers = ("i got", "i think it is", "i think it's")
    if has_answer_shape and "?" not in text and any(marker in lowered for marker in weak_answer_markers):
        return text
    non_answer_starters = (
        "can you",
        "could you",
        "why",
        "how",
        "what",
        "explain",
        "help",
        "give me",
        "show me",
        "hint",
        "next",
        "continue",
        "yes",
        "i don't know",
        "i dont know",
        "not sure",
    )
    is_short_answer = len(text) <= 200 and "?" not in text and not lowered.startswith(non_answer_starters)
    if is_short_answer and has_answer_shape:
        return text
    return None


def _build_probe_context(request: NormalizedChatRequest) -> str:
    user_texts = [
        _extract_message_text(item.get("content"))
        for item in request.conversation_history
        if item.get("role") == "user"
    ]
    user_texts.append(request.latest_user_text)
    return "\n\n".join(text[:600] for text in user_texts[-3:] if text).strip()
