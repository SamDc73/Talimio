"""Sandbox-backed local function tools."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from src.ai.tools.plan import FunctionToolDefinition, LocalToolTarget, ToolExecutor


RunCommandCallable = Callable[[str, str | None, str | None, int | None], Awaitable[dict[str, Any]]]
ReadFileCallable = Callable[[str], Awaitable[str]]
WriteFileCallable = Callable[[str, str], Awaitable[dict[str, Any]]]
ListDirCallable = Callable[[str, int], Awaitable[list[dict[str, Any]]]]
ResetCallable = Callable[[], Awaitable[dict[str, Any]]]


@dataclass(slots=True)
class SandboxToolContext:
    """Execution context for local sandbox tools."""

    scope_key: str
    run_command: RunCommandCallable | None = None
    read_file: ReadFileCallable | None = None
    write_file: WriteFileCallable | None = None
    list_dir: ListDirCallable | None = None
    reset: ResetCallable | None = None


def build_sandbox_function_tools(context: SandboxToolContext) -> list[FunctionToolDefinition]:
    """Build app-owned sandbox tools for a single request."""
    run_command_executor = _build_run_command_executor(context)
    read_file_executor = _build_read_file_executor(context)
    write_file_executor = _build_write_file_executor(context)
    list_dir_executor = _build_list_dir_executor(context)
    reset_executor = _build_reset_executor(context)
    return [
        FunctionToolDefinition(schema=_run_command_schema(), target=LocalToolTarget(execute=run_command_executor)),
        FunctionToolDefinition(schema=_read_file_schema(), target=LocalToolTarget(execute=read_file_executor)),
        FunctionToolDefinition(schema=_write_file_schema(), target=LocalToolTarget(execute=write_file_executor)),
        FunctionToolDefinition(schema=_list_dir_schema(), target=LocalToolTarget(execute=list_dir_executor)),
        FunctionToolDefinition(schema=_reset_schema(), target=LocalToolTarget(execute=reset_executor)),
    ]


def _build_run_command_executor(context: SandboxToolContext) -> ToolExecutor:
    async def executor(arguments: dict[str, Any]) -> dict[str, Any]:
        if context.run_command is None:
            msg = "Sandbox command execution is unavailable for this request"
            raise RuntimeError(msg)

        command = str(arguments.get("command", "")).strip()
        if not command:
            msg = "Field `command` is required"
            raise ValueError(msg)

        cwd_raw = arguments.get("cwd")
        cwd = str(cwd_raw).strip() if isinstance(cwd_raw, str) and cwd_raw.strip() else None
        user_raw = arguments.get("user")
        user = str(user_raw).strip() if isinstance(user_raw, str) and user_raw.strip() else None
        timeout_raw = arguments.get("timeout_seconds")
        timeout_seconds = int(timeout_raw) if timeout_raw is not None else None
        if timeout_seconds is not None and timeout_seconds <= 0:
            msg = "Field `timeout_seconds` must be greater than 0"
            raise ValueError(msg)

        return await context.run_command(command, cwd, user, timeout_seconds)

    return executor


def _build_read_file_executor(context: SandboxToolContext) -> ToolExecutor:
    async def executor(arguments: dict[str, Any]) -> dict[str, Any]:
        if context.read_file is None:
            msg = "Sandbox file reads are unavailable for this request"
            raise RuntimeError(msg)

        path = str(arguments.get("path", "")).strip()
        if not path:
            msg = "Field `path` is required"
            raise ValueError(msg)
        content = await context.read_file(path)
        return {"path": path, "content": content}

    return executor


def _build_write_file_executor(context: SandboxToolContext) -> ToolExecutor:
    async def executor(arguments: dict[str, Any]) -> dict[str, Any]:
        if context.write_file is None:
            msg = "Sandbox file writes are unavailable for this request"
            raise RuntimeError(msg)

        path = str(arguments.get("path", "")).strip()
        if not path:
            msg = "Field `path` is required"
            raise ValueError(msg)
        content = str(arguments.get("content", ""))
        result = await context.write_file(path, content)
        return {"path": path, **result}

    return executor


def _build_list_dir_executor(context: SandboxToolContext) -> ToolExecutor:
    async def executor(arguments: dict[str, Any]) -> dict[str, Any]:
        if context.list_dir is None:
            msg = "Sandbox directory listing is unavailable for this request"
            raise RuntimeError(msg)

        path_raw = arguments.get("path")
        path = str(path_raw).strip() if isinstance(path_raw, str) and path_raw.strip() else "."
        depth_raw = arguments.get("depth")
        depth = int(depth_raw) if depth_raw is not None else 2
        if depth < 1 or depth > 10:
            msg = "Field `depth` must be between 1 and 10"
            raise ValueError(msg)
        entries = await context.list_dir(path, depth)
        return {"path": path, "depth": depth, "entries": entries}

    return executor


def _build_reset_executor(context: SandboxToolContext) -> ToolExecutor:
    async def executor(_: dict[str, Any]) -> dict[str, Any]:
        if context.reset is None:
            msg = "Sandbox reset is unavailable for this request"
            raise RuntimeError(msg)
        return await context.reset()

    return executor


def _run_command_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run one shell command inside the active sandbox scope.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "command": {"type": "string"},
                    "cwd": {"type": "string"},
                    "user": {"type": "string", "enum": ["user", "root"]},
                    "timeout_seconds": {"type": "integer", "minimum": 1, "maximum": 600},
                },
                "required": ["command"],
            },
        },
    }


def _read_file_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a file from the active sandbox scope.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    }


def _write_file_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write full file contents into the active sandbox scope.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    }


def _list_dir_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories from the active sandbox scope.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "path": {"type": "string"},
                    "depth": {"type": "integer", "minimum": 1, "maximum": 10},
                },
            },
        },
    }


def _reset_schema() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": "reset",
            "description": "Reset the active sandbox scope state.",
            "parameters": {
                "type": "object",
                "additionalProperties": False,
                "properties": {},
            },
        },
    }
