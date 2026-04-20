# ruff: noqa: S101

import asyncio
import json
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch

from src.ai.client import LLMClient
from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget
from src.config.settings import get_settings


def _build_chat_response(content: str, tool_calls: list[dict[str, Any]] | None = None) -> object:
    message = type("Message", (), {"content": content, "tool_calls": tool_calls})()
    choice = type("Choice", (), {"message": message})()
    return type("CompletionResponse", (), {"choices": [choice]})()


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Any:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_request_scoped_wikipedia_tools_are_registered_and_executed(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("AI_ENABLE_HOSTED_WEB_SEARCH", "false")
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    client = LLMClient()

    captured_calls: list[dict[str, Any]] = []
    executed_arguments: list[dict[str, Any]] = []
    completion_call_count = 0

    async def resolve_wikipedia_pages(arguments: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0)
        executed_arguments.append(arguments)
        return {
            "pages": [
                {
                    "original_term": "Leibniz's notation",
                    "found": True,
                    "key": "Leibniz's_notation",
                    "title": "Leibniz's notation",
                    "is_disambiguation": False,
                }
            ]
        }

    async def fake_complete(**kwargs: Any) -> object:
        nonlocal completion_call_count
        await asyncio.sleep(0)
        captured_calls.append(kwargs)
        completion_call_count += 1
        if completion_call_count == 1:
            return _build_chat_response(
                "",
                tool_calls=[
                    {
                        "id": "call_resolve_wikipedia_pages",
                        "type": "function",
                        "function": {
                            "name": "resolve_wikipedia_pages",
                            "arguments": json.dumps({"terms": ["Leibniz's notation"]}),
                        },
                    }
                ],
            )
        return _build_chat_response("lesson finished")

    monkeypatch.setattr(client, "complete", fake_complete)

    result = await client.get_completion(
        messages=[{"role": "user", "content": "Write the lesson."}],
        model="anthropic/claude-3-7-sonnet",
        function_tools=[
            FunctionToolDefinition(
                schema={
                    "type": "function",
                    "function": {
                        "name": "resolve_wikipedia_pages",
                        "description": "Resolve canonical Wikipedia page keys.",
                        "parameters": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "terms": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                }
                            },
                            "required": ["terms"],
                        },
                    },
                },
                target=LocalToolTarget(execute=resolve_wikipedia_pages),
            )
        ],
    )

    assert result == "lesson finished"
    assert executed_arguments == [{"terms": ["Leibniz's notation"]}]
    assert captured_calls[0]["parallel_tool_calls"] is True
    assert any(
        isinstance(tool, dict)
        and tool.get("type") == "function"
        and isinstance(tool.get("function"), dict)
        and tool["function"].get("name") == "resolve_wikipedia_pages"
        for tool in captured_calls[0]["tools"]
    )
