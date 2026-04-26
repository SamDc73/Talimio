"""Assistant-only read tool adapters over learning capabilities."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget
from src.database.session import async_session_maker
from src.learning_capabilities.facade import LearningCapabilitiesFacade


ToolExecutor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
logger = logging.getLogger(__name__)


def build_learning_query_tools(*, user_id: uuid.UUID) -> list[FunctionToolDefinition]:
    """Return assistant read tools backed by the learning capability facade."""
    tool_specs: list[tuple[str, str, dict[str, Any]]] = [
        (
            "search_lessons",
            "Search lessons by title/description in the learner's owned courses.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "course_id": {"type": "string", "format": "uuid"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        ),
        (
            "list_relevant_courses",
            "List courses relevant to the learner's latest question.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": ["query"],
            },
        ),
        (
            "search_concepts",
            "Search concepts inside one adaptive course, including raw match and learner-state signals.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "query": {"type": "string"},
                    "course_id": {"type": "string", "format": "uuid"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                    "include_state": {"type": "boolean"},
                },
                "required": ["query", "course_id"],
            },
        ),
        (
            "get_course_state",
            "Get compact progress state for one course.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                },
                "required": ["course_id"],
            },
        ),
        (
            "get_course_outline_state",
            "Get a course lesson outline with generated, completed, and current flags.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                },
                "required": ["course_id"],
            },
        ),
        (
            "get_lesson_state",
            "Get compact state for one lesson.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                    "lesson_id": {"type": "string", "format": "uuid"},
                    "generate": {"type": "boolean"},
                },
                "required": ["course_id", "lesson_id"],
            },
        ),
        (
            "get_course_frontier",
            "Get adaptive frontier state for a course.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                },
                "required": ["course_id"],
            },
        ),
    ]

    definitions: list[FunctionToolDefinition] = []
    for tool_name, description, parameters in tool_specs:
        definitions.append(
            FunctionToolDefinition(
                schema={
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "description": description,
                        "parameters": parameters,
                    },
                },
                target=LocalToolTarget(execute=_build_query_executor(tool_name=tool_name, user_id=user_id)),
            )
        )
    return definitions


def _build_query_executor(*, tool_name: str, user_id: uuid.UUID) -> ToolExecutor:
    async def _execute(arguments: dict[str, Any]) -> dict[str, Any]:
        logger.info(
            "learning_capability.query_tool.execute",
            extra={
                "tool_name": tool_name,
                "user_id": str(user_id),
                "argument_keys": sorted(arguments.keys()),
            },
        )
        async with async_session_maker() as session:
            facade = LearningCapabilitiesFacade(session)
            result = await facade.execute_read_capability(
                user_id=user_id,
                capability_name=tool_name,
                payload=arguments,
            )
        logger.info(
            "learning_capability.query_tool.result",
            extra={
                "tool_name": tool_name,
                "user_id": str(user_id),
                "result_keys": sorted(result.keys()),
            },
        )
        return result

    return _execute
