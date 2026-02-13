"""Simple assistant service with streaming support."""

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncGenerator
from typing import Any, Literal
from uuid import UUID

import fitz  # PyMuPDF
from fastapi import HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai import AGENT_ID_ASSISTANT
from src.ai.client import LLMClient
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT
from src.books.models import Book
from src.courses.services.course_query_service import CourseQueryService
from src.storage.factory import get_storage_provider
from src.videos.models import Video

from .schemas import ChatRequest


logger = logging.getLogger(__name__)

ASSISTANT_RAG_TOP_K = 5
ASSISTANT_RAG_MAX_RESULTS = 3
ASSISTANT_PDF_CONTEXT_RADIUS_PAGES = 2
ASSISTANT_VIDEO_CONTEXT_WINDOW_SECONDS = 120


class ContextData(BaseModel):
    """Simple container for context data."""

    content: str
    source: str

    model_config = ConfigDict(frozen=True)


class NormalizedChatRequest(BaseModel):
    """Assistant request normalized from assistant-ui data stream payload."""

    message: str = Field(min_length=1)
    conversation_history: list[dict[str, str]] = Field(default_factory=list)
    model: str | None = None
    context_type: Literal["book", "video", "course"] | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, Any] | None = None

    model_config = ConfigDict(frozen=True)


def _sse_event(payload: dict[str, Any] | str) -> str:
    """Return a single SSE event line block."""
    encoded = payload if isinstance(payload, str) else json.dumps(payload)
    return f"data: {encoded}\n\n"


def _extract_message_text(content: Any) -> str:
    """Extract plain text from assistant-ui language model message content."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    text_parts: list[str] = []
    for part in content:
        if not isinstance(part, dict):
            continue
        part_type = part.get("type")
        if part_type == "text" and isinstance(part.get("text"), str):
            text_parts.append(part["text"])

    return "".join(text_parts).strip()


def _normalize_chat_request(request: ChatRequest) -> NormalizedChatRequest:
    """Normalize assistant-ui runtime request body into assistant domain request."""
    flattened: list[dict[str, str]] = []

    for item in request.messages:
        if item.role not in {"user", "assistant"}:
            continue
        text = _extract_message_text(item.content)
        if not text:
            continue
        flattened.append({"role": item.role, "content": text})

    if not flattened:
        msg = "No user/assistant messages were provided"
        raise ValueError(msg)

    last_user_index = -1
    for index in range(len(flattened) - 1, -1, -1):
        if flattened[index]["role"] == "user":
            last_user_index = index
            break

    if last_user_index < 0:
        msg = "Latest user message is required"
        raise ValueError(msg)

    message = flattened[last_user_index]["content"].strip()
    if not message:
        msg = "Latest user message cannot be empty"
        raise ValueError(msg)

    if request.pending_quote and request.pending_quote.strip():
        message = f"{request.pending_quote.strip()}\n\n{message}"

    return NormalizedChatRequest(
        message=message,
        conversation_history=flattened[:last_user_index],
        model=request.modelName or request.model,
        context_type=request.context_type,
        context_id=request.context_id,
        context_meta=request.context_meta,
    )


async def assistant_chat(
    request: ChatRequest,
    user_id: UUID,
    session: AsyncSession,
) -> AsyncGenerator[str, None]:
    """Stream chat responses with optional context using ui-message-stream protocol."""
    message_id = str(uuid.uuid4())
    try:
        # Emit start immediately so the client can render streaming state while prep runs.
        yield _sse_event({"type": "start", "messageId": message_id})

        normalized_request = _normalize_chat_request(request)

        # Build messages with context if available
        messages = await _build_messages(normalized_request, user_id, session)

        # Run completion through shared LLM client so memories and MCP tools are available
        llm_client = LLMClient(agent_id=AGENT_ID_ASSISTANT)
        stream = await llm_client.get_completion(
            messages=messages,
            user_id=user_id,
            model=normalized_request.model,
            stream=True,
        )

        saw_any_content = False

        async for delta in stream:
            if not delta:
                continue
            saw_any_content = True
            yield _sse_event({"type": "text-delta", "textDelta": delta})

        if not saw_any_content:
            logger.warning("Assistant returned empty streamed response for user %s", user_id)
            fallback_content = "I couldn't retrieve results right now. Please try again."
            yield _sse_event({"type": "text-delta", "textDelta": fallback_content})

        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "stop",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")

    except Exception:
        logger.exception("Chat failed for user %s", user_id)
        error_msg = "Sorry, I'm having trouble responding right now. Please try again."
        yield _sse_event({"type": "error", "errorText": error_msg})
        yield _sse_event(
            {
                "type": "finish",
                "finishReason": "error",
                "usage": {"promptTokens": 0, "completionTokens": 0},
            }
        )
        yield _sse_event("[DONE]")


async def _build_messages(request: NormalizedChatRequest, user_id: UUID, session: AsyncSession) -> list[dict[str, str]]:
    """Build message list with optional context."""
    context_parts = []

    # Get immediate context (current page, timestamp, lesson)
    if request.context_type and request.context_id:
        context_meta = request.context_meta or {}
        context_meta["user_id"] = user_id
        context_data = await get_context(
            context_type=request.context_type,
            resource_id=request.context_id,
            context_meta=context_meta,
            session=session,
        )
        if context_data:
            context_parts.append(f"Current {request.context_type} context:\n{context_data.content}")
            logger.debug("Added immediate context from %s", context_data.source)

    # Get semantic context (RAG search)
    if request.context_type and request.context_id:
        semantic_results = await _get_rag_context(request, user_id, session)

        if semantic_results:
            # Limit how many results we inject into the prompt.
            max_results = max(ASSISTANT_RAG_MAX_RESULTS, 0)
            top = [] if max_results <= 0 else semantic_results[:max_results]
            blocks: list[str] = []

            # Simple suffix mapping for metadata
            suffix_map = {
                "book": lambda meta: f"\n[page {meta.get('page')}]" if meta.get("page") is not None else "",
                "video": lambda meta: f"\n[time {meta.get('start')}-{meta.get('end')}s]"
                if meta.get("start") is not None and meta.get("end") is not None
                else "",
            }

            for r in top:
                content = getattr(r, "content", str(r))
                meta = getattr(r, "metadata", {}) or {}
                suffix = suffix_map.get(request.context_type, lambda _: "")(meta)
                blocks.append(f"{content}{suffix}")

            if blocks:
                semantic_text = "\n\n".join(blocks)
                context_parts.append(f"Related {request.context_type} content:\n{semantic_text}")
                logger.debug("Added %d semantic search results", len(blocks))

    # Use unified prompt that handles context intelligently
    system_prompt = ASSISTANT_CHAT_SYSTEM_PROMPT

    # Build message list
    messages = [{"role": "system", "content": system_prompt}]

    # Add conversation history
    messages.extend(request.conversation_history)

    # Build user message with context
    user_message = request.message
    if context_parts:
        context_text = "\n\n---\n\n".join(context_parts)
        user_message = f"{request.message}\n\n[Context:\n{context_text}\n]"

    messages.append({"role": "user", "content": user_message})

    return messages


def _extract_leading_blockquote(text: str) -> str:
    """Return leading Markdown blockquote content (without the '>').

    Only reads contiguous leading lines that begin with '>' (optionally preceded by spaces).
    Strips a single '>' and a following space if present.
    """
    try:
        lines = text.splitlines()
        out: list[str] = []
        for line in lines:
            i = 0
            # skip leading spaces
            while i < len(line) and line[i] == " ":
                i += 1
            if i < len(line) and line[i] == ">":
                i += 1
                if i < len(line) and line[i] == " ":
                    i += 1
                out.append(line[i:])
                continue
            break
        return "\n".join(out).strip()
    except Exception:
        return ""


async def _get_rag_context(request: NormalizedChatRequest, user_id: UUID, session: AsyncSession) -> list:
    """Get semantic search results for any context type.

    Uses the user's quoted selection (if present) as the primary query, falling back to the full message.
    """
    if not request.context_id:
        return []

    # Prefer leading blockquote as query for better retrieval relevance
    query_text = _extract_leading_blockquote(request.message) or request.message

    try:
        if request.context_type == "course":
            from src.ai.rag.service import RAGService
            logger.info(
                "Searching for course documents with course_id: %s, query: %s...",
                request.context_id,
                (query_text[:50] + ("..." if len(query_text) > 50 else "")),
            )

            rag_service = RAGService()
            results = await rag_service.search_course_documents(
                session=session,
                course_id=request.context_id,
                query=query_text,
                top_k=ASSISTANT_RAG_TOP_K,
            )
            logger.info("Retrieved %d RAG results for course %s", len(results), request.context_id)
            if results:
                logger.debug("First result preview: %s", results[0].content[:100])
            return results

        if request.context_type in ("book", "video"):
            from uuid import UUID as _UUID

            from sqlalchemy import select as _select

            from src.ai.rag.embeddings import VectorRAG
            model_map = {"book": ("src.books.models", "Book"), "video": ("src.videos.models", "Video")}
            module_name, model_name = model_map[request.context_type]

            # Dynamic import to avoid circular imports
            import importlib

            module = importlib.import_module(module_name)
            model_class = getattr(module, model_name)

            rag = VectorRAG()
            # Ownership check
            resource = await session.scalar(
                _select(model_class).where(
                    model_class.id == _UUID(str(request.context_id)), model_class.user_id == user_id
                )
            )
            if not resource:
                return []

            return await rag.search(
                session,
                doc_type=request.context_type,
                query=query_text,
                limit=ASSISTANT_RAG_TOP_K,
                doc_id=resource.id,
            )

        return []

    except Exception:
        logger.exception("RAG search failed for %s_id: %s", request.context_type, request.context_id)
        return []


async def _book_context(
    resource_id: UUID,
    context_meta: dict[str, Any],
    session: AsyncSession,
) -> ContextData | None:
    """Get text from PDF pages around current page.

    Uses asyncio.to_thread to offload PyMuPDF parsing to a background thread,
    preventing event loop blocking as recommended by FastAPI best practices.
    """
    if "page" not in context_meta:
        return None

    current_page = context_meta["page"]
    if current_page < 0:
        logger.warning("Invalid page number: %s", current_page)
        return None
    user_id = context_meta.get("user_id")

    query = select(Book).where(Book.id == resource_id)
    if user_id:
        query = query.where(Book.user_id == user_id)
    book = await session.scalar(query)
    if not book or not book.file_path:
        return None

    storage = get_storage_provider()
    file_content = await storage.download(book.file_path)

    def _extract_pdf_context(content: bytes, page_index: int) -> tuple[str | None, str | None]:
        """Parse PDF synchronously and return (joined_text, source_label)."""
        doc = fitz.open(stream=content, filetype="pdf")
        try:
            start_page = max(0, page_index - ASSISTANT_PDF_CONTEXT_RADIUS_PAGES)
            end_page = min(doc.page_count - 1, page_index + ASSISTANT_PDF_CONTEXT_RADIUS_PAGES)

            text_parts: list[str] = []
            for page_num in range(start_page, end_page + 1):
                page_text = doc.load_page(page_num).get_text().strip()
                if page_text:
                    text_parts.append(page_text)

            if not text_parts:
                return None, None

            source = f"pages {start_page + 1}-{end_page + 1}"
            return "\n\n".join(text_parts), source
        finally:
            doc.close()

    # Offload heavy PDF parsing work to a thread
    joined_text, source = await asyncio.to_thread(_extract_pdf_context, file_content, current_page)
    if not joined_text:
        return None

    # Build human-readable source label safely
    title = getattr(book, "title", "Document")
    source_label = f"{title}: {source}" if source else title

    return ContextData(
        content=joined_text,
        source=source_label,
    )


async def _video_context(
    resource_id: UUID,
    context_meta: dict[str, Any],
    session: AsyncSession,
) -> ContextData | None:
    """Get transcript window around the current timestamp."""
    if "timestamp" not in context_meta or "user_id" not in context_meta:
        return None

    timestamp = context_meta["timestamp"]
    if timestamp < 0:
        logger.warning("Invalid timestamp: %s", timestamp)
        return None
    user_id = context_meta["user_id"]

    result = await session.execute(
        select(Video.title, Video.transcript_data).where(Video.id == resource_id, Video.user_id == user_id)
    )
    row = result.first()
    if not row:
        return None

    title = row.title
    transcript_data = row.transcript_data or {}
    segments = transcript_data.get("segments") or []
    if not segments:
        return None

    window_start = max(0.0, timestamp - ASSISTANT_VIDEO_CONTEXT_WINDOW_SECONDS)
    window_end = timestamp + ASSISTANT_VIDEO_CONTEXT_WINDOW_SECONDS

    window_segments = []
    for seg in segments:
        start = seg.get("start")
        end = seg.get("end")
        text = seg.get("text")
        if text is None or start is None or end is None:
            continue
        if float(end) >= window_start and float(start) <= window_end:
            window_segments.append(str(text))

    if not window_segments:
        return None

    transcript = " ".join(window_segments)

    return ContextData(
        content=f"[Currently at {timestamp:.1f} seconds]\n\n{transcript}",
        source=title or "Video",
    )


async def _course_context(
    resource_id: UUID,
    context_meta: dict[str, Any],
    session: AsyncSession,
) -> ContextData | None:
    """Get course overview and optionally lesson content."""
    if "user_id" not in context_meta:
        return None

    user_id = context_meta["user_id"]
    lesson_id = context_meta.get("lesson_id")

    course_query_service = CourseQueryService(session)
    try:
        course_response = await course_query_service.get_course(resource_id, user_id)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            return None
        logger.exception("Failed to load course context for course %s", resource_id)
        return None
    except Exception:
        logger.exception("Failed to load course context for course %s", resource_id)
        return None

    course = course_response.model_dump()

    # Build course header
    parts = [
        f"Course: {course.get('title', 'Untitled Course')}",
        f"Description: {course.get('description', 'No description')}",
        "",
    ]

    # Get all lessons from modules
    modules = course.get("modules") or course.get("nodes", [])
    lessons = []
    for module in modules:
        module_lessons = module.get("lessons", []) if isinstance(module, dict) else getattr(module, "lessons", [])
        lessons.extend(module_lessons)

    if not lessons:
        return ContextData(
            content="\n".join(parts),
            source=course.get("title", "Untitled Course"),
        )

    # List all lessons
    parts.append("Lessons:")
    current_lesson = None
    for lesson in lessons:
        lesson_id_str = lesson.get("id") if isinstance(lesson, dict) else getattr(lesson, "id", None)
        lesson_title = lesson.get("title") if isinstance(lesson, dict) else getattr(lesson, "title", "Untitled")

        is_current = lesson_id and str(lesson_id_str) == str(lesson_id)
        parts.append(f"- {lesson_title}{' [CURRENT]' if is_current else ''}")

        if is_current:
            current_lesson = lesson

    # Add current lesson content if available
    if current_lesson:
        parts.extend(["", f"Current lesson: {current_lesson.get('title', 'Untitled')}"])

        content = current_lesson.get("content")
        lesson_status = current_lesson.get("status")

        if content:
            parts.append(content)
        elif lesson_status in ["pending", "generating"]:
            parts.append("[Lesson is being generated...]")
        else:
            parts.append("[No content available]")

    return ContextData(
        content="\n".join(parts),
        source=course.get("title", "Untitled Course"),
    )


_HANDLERS = {
    "book": _book_context,
    "video": _video_context,
    "course": _course_context,
}


async def get_context(
    context_type: str,
    resource_id: UUID,
    context_meta: dict[str, Any] | None = None,
    session: AsyncSession | None = None,
) -> ContextData | None:
    """Get context for any resource type."""
    if not resource_id:
        return None

    handler = _HANDLERS.get(context_type)
    if not handler:
        logger.error("Unknown context type: %s", context_type)
        return None

    if session is None:
        msg = "Database session is required to build assistant context"
        raise RuntimeError(msg)

    try:
        return await handler(resource_id, context_meta or {}, session)
    except (ValueError, AttributeError, KeyError):
        logger.exception("Context validation error")
        return None
    except Exception:
        logger.exception("Context retrieval failed: type=%s, resource=%s", context_type, resource_id)
        return None
