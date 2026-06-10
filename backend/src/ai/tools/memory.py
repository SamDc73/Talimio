"""Read-only learner pedagogical memory search tool."""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from pydantic import JsonValue

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget


_DEFAULT_LIMIT = 5
_MIN_LIMIT = 1
_MAX_LIMIT = 10

_LEARNER_MEMORY_SEARCH_TOOL_SCHEMA: dict[str, object] = {
    "type": "function",
    "function": {
        "name": "search_learner_memory",
        "description": (
            "Search this learner's pedagogical memory: distilled notes from past lesson critiques, "
            "what teaching approaches worked or did not, and study habits. Use it when tailoring "
            "content, examples, pacing, or explanations to this learner. Each result has a note "
            "(the fact), a scene_trace (when/how it was learned), and provenance. Returns an empty "
            "result set when nothing relevant is stored — do not retry with broader queries."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": _MIN_LIMIT, "maximum": _MAX_LIMIT, "default": _DEFAULT_LIMIT},
            },
            "required": ["query"],
        },
    },
}


def build_learner_memory_search_tool(
    *,
    user_id: uuid.UUID,
    course_id: uuid.UUID | None = None,
) -> FunctionToolDefinition:
    """Return the read-only `search_learner_memory` function tool scoped to one learner."""

    async def execute(arguments: Mapping[str, object]) -> dict[str, JsonValue]:
        query = str(arguments.get("query") or "").strip()
        if not query:
            msg = "Field `query` is required"
            raise ValueError(msg)
        limit = _normalize_limit(arguments.get("limit"))

        # Call-time import: the session maker is patched per-process in tests
        # and this tool opens its own short-lived, read-only session.
        from src.database.session import async_session_maker
        from src.memory.services.notes_search import search_learner_notes

        async with async_session_maker() as session:
            hits = await search_learner_notes(
                session,
                user_id=user_id,
                query=query,
                course_id=course_id,
                limit=limit,
            )

        return {
            "results": [
                {
                    "note": hit.note,
                    "scene_trace": hit.scene_trace,
                    "occurred_at": hit.occurred_at.isoformat(),
                    "source": hit.source_kind,
                }
                for hit in hits
            ],
            "found": len(hits),
        }

    return FunctionToolDefinition(
        schema=_LEARNER_MEMORY_SEARCH_TOOL_SCHEMA,
        target=LocalToolTarget(execute=execute),
    )


def _normalize_limit(raw_limit: object) -> int:
    if isinstance(raw_limit, bool) or not isinstance(raw_limit, int):
        return _DEFAULT_LIMIT
    return max(_MIN_LIMIT, min(_MAX_LIMIT, raw_limit))
