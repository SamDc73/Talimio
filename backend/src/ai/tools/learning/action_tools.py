"""Assistant-only action tool adapters over learning capabilities."""

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget
from src.database.session import async_session_maker
from src.learning_capabilities.facade import LearningCapabilitiesFacade


ToolExecutor = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]
logger = logging.getLogger(__name__)


def build_learning_action_tools(*, user_id: uuid.UUID) -> list[FunctionToolDefinition]:
    """Return assistant write tools backed by learning capabilities."""
    tool_specs: list[tuple[str, str, dict[str, Any]]] = [
        (
            "create_course",
            "Create a new course from a learner prompt. Requires confirmation.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "prompt": {"type": "string"},
                    "adaptive_enabled": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["prompt"],
            },
        ),
        (
            "append_course_lesson",
            "Append a lesson to an existing course. Requires confirmation.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                    "lesson_title": {"type": "string"},
                    "lesson_description": {"type": "string"},
                    "module_name": {"type": "string"},
                    "generate_content": {"type": "boolean"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["course_id", "lesson_title"],
            },
        ),
        (
            "extend_lesson_with_context",
            "Append generated content to a lesson body using injected context. Requires confirmation.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                    "lesson_id": {"type": "string", "format": "uuid"},
                    "context": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["course_id", "lesson_id", "context"],
            },
        ),
        (
            "regenerate_lesson_with_context",
            "Regenerate lesson content with injected context. Requires confirmation.",
            {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "course_id": {"type": "string", "format": "uuid"},
                    "lesson_id": {"type": "string", "format": "uuid"},
                    "context": {"type": "string"},
                    "confirmed": {"type": "boolean"},
                },
                "required": ["course_id", "lesson_id", "context"],
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
                target=LocalToolTarget(execute=_build_action_executor(tool_name=tool_name, user_id=user_id)),
            )
        )
    return definitions


def _build_action_executor(*, tool_name: str, user_id: uuid.UUID) -> ToolExecutor:
    async def _execute(arguments: dict[str, Any]) -> dict[str, Any]:
        logger.info(
            "learning_capability.action_tool.execute",
            extra={
                "tool_name": tool_name,
                "user_id": str(user_id),
                "argument_keys": sorted(arguments.keys()),
            },
        )
        async with async_session_maker() as session:
            facade = LearningCapabilitiesFacade(session)
            result = await facade.execute_action_capability(
                user_id=user_id,
                capability_name=tool_name,
                payload=arguments,
            )
            if result.get("status") == "completed":
                await session.commit()
            else:
                await session.rollback()
            logger.info(
                "learning_capability.action_tool.result",
                extra={
                    "tool_name": tool_name,
                    "user_id": str(user_id),
                    "status": result.get("status"),
                },
            )
            return result

    return _execute
