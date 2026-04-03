
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.models import PlanAction


"""AI-powered code execution service using E2B Code Interpreter sandboxes.

Fully autonomous execution with fast-path optimization:
- Fast-path: Common languages execute instantly via templates (<50ms)
- Cached plans: Previously seen patterns reuse cached execution plans (<100ms)
- AI fallback: Exotic languages/errors trigger AI planner (2s)

Sandboxes are reused per user+course with configurable TTL for compute efficiency.
"""

import asyncio
import hashlib
import json
import logging
import posixpath
import re
import shlex
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar

from fastapi import status
from sqlalchemy import update
from sqlalchemy.exc import SQLAlchemyError

from src.ai.service import get_ai_service
from src.ai.tools.sandbox import SandboxToolContext
from src.config.settings import get_settings
from src.courses.models import Course, Lesson

from .setup_commands_normalizer import normalize_setup_commands


# Prefer AsyncSandbox; fall back if package layout differs
_AsyncSandbox: Any | None = None
try:  # e2b-code-interpreter >= 2.x
    from e2b_code_interpreter import AsyncSandbox as _ImportedAsyncSandbox

    _AsyncSandbox = _ImportedAsyncSandbox
except ImportError:
    pass

AsyncSandbox: Any | None = _AsyncSandbox

_AuthenticationException: type[Exception] = Exception
_InvalidArgumentException: type[Exception] = Exception
_NotEnoughSpaceException: type[Exception] = Exception
_RateLimitException: type[Exception] = Exception
_TimeoutException: type[Exception] = Exception
_SandboxException: type[Exception] = Exception
_CommandExitException: type[Exception] = Exception

try:
    from e2b.exceptions import (
        AuthenticationException as _AuthenticationException,
        InvalidArgumentException as _InvalidArgumentException,
        NotEnoughSpaceException as _NotEnoughSpaceException,
        RateLimitException as _RateLimitException,
        SandboxException as _SandboxException,
        TimeoutException as _TimeoutException,
    )
    from e2b.sandbox.commands.command_handle import (
        CommandExitException as _CommandExitException,
    )
except ImportError:
    pass

AuthenticationException = _AuthenticationException
InvalidArgumentException = _InvalidArgumentException
NotEnoughSpaceException = _NotEnoughSpaceException
RateLimitException = _RateLimitException
TimeoutException = _TimeoutException
SandboxException = _SandboxException
CommandExitException = _CommandExitException
logger = logging.getLogger(__name__)

APT_GET_UPDATE_COMMAND = "apt-get update"
HOME_USER_DIR = "/home/user"
WORKSPACES_DIR = f"{HOME_USER_DIR}/workspaces"

# Trim noisy SDK logs by default; configurable via env
E2B_SDK_LOG_LEVEL = get_settings().E2B_SDK_LOG_LEVEL.upper()
try:
    _e2b_level = getattr(logging, E2B_SDK_LOG_LEVEL, logging.WARNING)
except (AttributeError, TypeError):
    _e2b_level = logging.WARNING
for _name in ("e2b.api", "e2b.sandbox_async.main"):
    logging.getLogger(_name).setLevel(_e2b_level)


@dataclass
class ExecutionResult:
    """Normalized result payload returned to API layer."""

    stdout: str | None
    stderr: str | None
    status: str | None
    time: float | None
    memory: float | None


@dataclass(slots=True)
class WorkspaceFile:
    """Simple data carrier for workspace file payloads."""

    path: str
    content: str


class CodeExecutionError(RuntimeError):
    """Domain error raised when sandbox execution fails."""

    def __init__(self, message: str, *, status_code: int, error_code: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


# Fast-path templates for instant execution (no AI overhead)
FAST_PATH_TEMPLATES = {
    "python": {"file": "main.py", "cmd": "python3 main.py"},
    "javascript": {"file": "main.js", "cmd": "node main.js"},
    "typescript": {"file": "main.ts", "cmd": "npx tsx main.ts"},
    "go": {"file": "main.go", "cmd": "go run main.go"},
    "rust": {"file": "main.rs", "cmd": "rustc main.rs -o main && ./main"},
    "java": {"file": "Main.java", "cmd": "javac Main.java && java Main"},
    "c": {"file": "main.c", "cmd": "gcc main.c -o main && ./main"},
    "cpp": {"file": "main.cpp", "cmd": "g++ main.cpp -o main && ./main"},
    "ruby": {"file": "main.rb", "cmd": "ruby main.rb"},
    "php": {"file": "main.php", "cmd": "php main.php"},
    "r": {"file": "script.R", "cmd": "Rscript script.R"},
    "lua": {"file": "script.lua", "cmd": "lua script.lua"},
    "swift": {"file": "main.swift", "cmd": "swift main.swift"},
    "kotlin": {"file": "Main.kt", "cmd": "kotlinc Main.kt -include-runtime -d main.jar && java -jar main.jar"},
    "scala": {"file": "Main.scala", "cmd": "scala Main.scala"},
}


# Fast-path installers provision missing runtimes before executing templates
FAST_PATH_INSTALLERS = {
    "go": [
        APT_GET_UPDATE_COMMAND,
        ("DEBIAN_FRONTEND=noninteractive DEBCONF_NOWARNINGS=yes apt-get install -y --no-install-recommends golang-go"),
    ],
    "rust": [
        APT_GET_UPDATE_COMMAND,
        (
            "DEBIAN_FRONTEND=noninteractive DEBCONF_NOWARNINGS=yes "
            "apt-get install -y --no-install-recommends rustc cargo"
        ),
    ],
}


class CodeExecutionService:
    """AI-powered E2B execution service - handles any language autonomously."""

    # In-memory session cache: key -> (created_time, sandbox)
    _sessions: ClassVar[dict[str, tuple[float, Any]]] = {}
    # In-memory plan cache: cache_key -> ExecutionPlan (simple dict, no Redis)
    _plan_cache: ClassVar[dict[str, Any]] = {}
    # Course setup tracking: sandbox_key -> bool
    _setup_done_by_key: ClassVar[dict[str, bool]] = {}
    # Runtime process handles keyed by sandbox scope then pid.
    _runtime_handles: ClassVar[dict[str, dict[int, Any]]] = {}
    # Incremental output offsets keyed by "<scope_key>:<pid>".
    _runtime_output_offsets: ClassVar[dict[str, tuple[int, int]]] = {}
    # Runtime install lock per sandbox to avoid apt/dpkg lock contention under concurrency.
    _runtime_install_locks: ClassVar[dict[str, asyncio.Lock]] = {}

    def __init__(self, session: AsyncSession) -> None:
        ttl = get_settings().E2B_SANDBOX_TTL
        self.sandbox_ttl = max(60, ttl)
        self._ai_service = get_ai_service()
        self._session = session
        self._apt_sentinel = f"{HOME_USER_DIR}/.talimio_apt_updated"
        self._language_sentinel_prefix = f"{HOME_USER_DIR}/.talimio_lang_"
        self._workspace_root = WORKSPACES_DIR

    def _session_key(self, user_id: str | None, course_id: str | None) -> str:
        """Generate sandbox key per user+course (not per lesson)."""
        return f"{user_id or '_'}:{course_id or '_'}"

    async def _get_sandbox(self, key: str) -> Any:
        now = time.time()
        # Evict expired
        stale = []
        for k, (created, _sbx) in self._sessions.items():
            if now - created > self.sandbox_ttl:
                stale.append(k)
        for k in stale:
            try:
                _created, sbx = self._sessions.pop(k)
                self._setup_done_by_key.pop(k, None)
                self._runtime_install_locks.pop(self._runtime_lock_key(sbx), None)
                # Best effort async close
                closer = getattr(sbx, "close", None)
                if callable(closer):
                    await _maybe_await(closer())
                else:
                    acloser = getattr(sbx, "aclose", None)
                    if callable(acloser):
                        await _maybe_await(acloser())
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.exception("Failed to close sandbox for key %s", k)

        # Reuse if present
        if key in self._sessions:
            sbx = self._sessions[key][1]
            if await self._refresh_sandbox_timeout(sbx):
                logger.debug("Reusing E2B sandbox for key=%s", key)
                return sbx
            logger.warning("Discarding stale sandbox after timeout refresh failure key=%s", key)
            await self._reset_session(key)

        if AsyncSandbox is None:
            msg = "e2b-code-interpreter AsyncSandbox not available"
            raise RuntimeError(msg)

        # Create fresh sandbox
        # We allow internet access to enable on-demand installs later if desired.
        logger.info("Creating new E2B sandbox key=%s ttl=%s", key, self.sandbox_ttl)
        try:
            sbx = await AsyncSandbox.create(timeout=self.sandbox_ttl)
        except (OSError, RuntimeError, SandboxException, TimeoutException, RateLimitException) as exc:
            # Retry once on transient network/loop cleanup issues
            logger.warning("Sandbox create failed once for key=%s: %s; retrying", key, exc)
            await asyncio.sleep(0.2)
            sbx = await AsyncSandbox.create(timeout=self.sandbox_ttl)
        self._sessions[key] = (now, sbx)
        return sbx

    async def _refresh_sandbox_timeout(self, sbx: Any) -> bool:
        """Best-effort sandbox timeout refresh for reused sessions."""
        refresher = getattr(sbx, "set_timeout", None)
        if not callable(refresher):
            return True
        try:
            await _maybe_await(refresher(self.sandbox_ttl))
            return True
        except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
            logger.debug("Failed to refresh sandbox timeout", exc_info=True)
            return False

    async def execute(
        self,
        *,
        source_code: str,
        language: str,
        stdin: str | None = None,
        user_id: str | None = None,
        course_id: str | None = None,
        lesson_id: str | None = None,
        setup_commands: list[str] | None = None,
        files: Sequence[WorkspaceFile] | None = None,
        entry_file: str | None = None,
        workspace_id: str | None = None,
    ) -> ExecutionResult:
        """Execute code with fast-path optimization and course-scoped sandboxes.

        Execution flow:
        1. Get/create course-scoped sandbox
        2. Run course setup commands (once per course)
        3. Try fast-path template (instant)
        4. Try cached plan (if seen before)
        5. Fallback to AI planner
        """
        key = self._session_key(user_id, course_id)
        sbx = await self._get_sandbox(key)

        raw_setup_commands = list(setup_commands or [])
        normalized_setup_commands = normalize_setup_commands(raw_setup_commands)
        if course_id and normalized_setup_commands != raw_setup_commands:
            await self._persist_normalized_setup_commands(course_id, normalized_setup_commands)

        # Run course setup commands once per sandbox
        if course_id and normalized_setup_commands and not self._setup_done_by_key.get(key):
            await self._run_course_setup(
                sbx,
                setup_key=key,
                course_id=course_id,
                setup_commands=normalized_setup_commands,
            )

        workspace_context: dict[str, Any] | None = None
        if files:
            workspace_context = await self._prepare_workspace(
                sbx=sbx,
                files=files,
                workspace_id=workspace_id,
                course_id=course_id,
                lesson_id=lesson_id,
                entry_file=entry_file,
            )

        code_sig = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:8]
        logger.debug("Run start key=%s lang=%s code_sig=%s size=%d", key, language, code_sig, len(source_code))

        is_workspace_mode = workspace_context is not None

        norm_lang = language.lower().strip()
        if norm_lang in FAST_PATH_INSTALLERS:
            await self._ensure_runtime(sbx, norm_lang)

        if is_workspace_mode:
            workspace_result = await self._try_workspace_fast_path(
                sbx=sbx,
                language=norm_lang,
                workspace_entry_file=workspace_context["entry_file"] if workspace_context else None,
                workspace_root=workspace_context["workspace_dir"] if workspace_context else None,
            )
            if workspace_result is not None and workspace_result.status != "error":
                logger.debug("Workspace fast-path success lang=%s", norm_lang)
                return workspace_result

        # Try fast-path first (instant for common languages)
        if not is_workspace_mode and norm_lang in FAST_PATH_TEMPLATES:
            logger.info("Fast-path provisioning check lang=%s key=%s", norm_lang, key)
            try:
                result = await self._fast_path_execute(sbx, norm_lang, source_code, stdin)
                if result.status != "error":
                    logger.debug("Fast-path success lang=%s", norm_lang)
                    return result
                # Fast-path failed, fall through to AI
                logger.debug("Fast-path failed lang=%s, trying AI", norm_lang)
            except (
                OSError,
                RuntimeError,
                TimeoutException,
                RateLimitException,
                InvalidArgumentException,
                NotEnoughSpaceException,
                AuthenticationException,
                SandboxException,
                CommandExitException,
            ):
                logger.debug("Fast-path exception lang=%s, trying AI", norm_lang, exc_info=True)

        # Try cached plan
        cache_key: str | None = None
        cached_plan: Any | None = None
        if not is_workspace_mode:
            cache_key = self._plan_cache_key(course_id, language, source_code)
            cached_plan = self._plan_cache.get(cache_key)
            if cached_plan:
                logger.debug("Using cached plan cache_key=%s", cache_key)
                result = await self._apply_execution_plan(
                    sbx=sbx,
                    plan=cached_plan,
                    source_code=source_code,
                    language=language,
                    lesson_id=lesson_id,
                    is_workspace_mode=is_workspace_mode,
                )
                if result.status != "error":
                    return result
                logger.debug("Cached plan failed, trying AI")

        # AI fallback
        result = await self._plan_and_execute_with_ai(
            sbx=sbx,
            source_code=source_code,
            language=language,
            stdin=stdin,
            user_id=user_id,
            lesson_id=lesson_id,
            cache_key=cache_key,
            scope_key=key,
            workspace_entry_file=workspace_context["entry_file"] if workspace_context else None,
            workspace_root=workspace_context["workspace_dir"] if workspace_context else None,
            workspace_files=workspace_context["manifest"] if workspace_context else None,
            workspace_identifier=workspace_context["identifier"] if workspace_context else workspace_id,
            is_workspace_mode=is_workspace_mode,
        )

        # Detect sandbox context restarts and reset the session to keep things healthy
        if self._is_context_restart(result):
            logger.warning("E2B context restarted during run key=%s lang=%s code_sig=%s", key, language, code_sig)
            await self._reset_session(key)
            # Return actionable message
            hint = (
                "The execution context was restarted by the sandbox (likely due to memory/time limits). "
                "Try reducing data sizes or splitting the work into smaller steps. The environment was reset; re-run if needed."
            )
            result.stderr = (result.stderr + "\n" + hint).strip() if result.stderr else hint
            result.status = result.status or "restarted"

        return result

    async def start_process(
        self,
        *,
        command: str,
        user_id: str | None,
        course_id: str | None,
        workspace_id: str | None,
        cwd: str | None,
        env: dict[str, str] | None,
        user: str | None,
    ) -> dict[str, Any]:
        """Start a long-lived command process in the scoped sandbox."""
        key = self._session_key(user_id, course_id)
        sbx = await self._get_sandbox(key)

        normalized_command = command.strip()
        if not normalized_command:
            msg = "Runtime command must not be empty"
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_command")

        run_user = (user or "user").strip() or "user"
        if run_user not in {"user", "root"}:
            msg = "Runtime user must be either 'user' or 'root'"
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_user")

        normalized_env = self._normalize_runtime_env(env)
        runtime_cwd = self._resolve_runtime_working_directory(
            course_id=course_id,
            workspace_id=workspace_id,
            cwd=cwd,
        )
        if runtime_cwd:
            await self._ensure_runtime_directory_exists(sbx, runtime_cwd)

        try:
            try:
                handle = await sbx.commands.run(
                    cmd=normalized_command,
                    background=True,
                    stdin=True,
                    envs=normalized_env or None,
                    user=run_user,
                    cwd=runtime_cwd,
                    timeout=0,
                    request_timeout=30,
                )
            except TypeError:
                handle = await sbx.commands.run(
                    cmd=normalized_command,
                    background=True,
                    stdin=True,
                    envs=normalized_env or None,
                    user=run_user,
                    timeout=0,
                    request_timeout=30,
                )
        except CommandExitException as exc:
            error_text = getattr(exc, "stderr", None) or str(exc)
            msg = self._command_failure_message(normalized_command, error_text)
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="command_failed") from exc
        except TimeoutException as exc:
            msg = "Starting runtime process timed out"
            raise CodeExecutionError(msg, status_code=status.HTTP_504_GATEWAY_TIMEOUT, error_code="timeout") from exc
        except (
            OSError,
            RuntimeError,
            RateLimitException,
            InvalidArgumentException,
            NotEnoughSpaceException,
            AuthenticationException,
            SandboxException,
        ) as exc:
            msg = f"Failed to start runtime process: {exc}"
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="runtime_start_failed") from exc

        process_id = getattr(handle, "pid", None)
        if not isinstance(process_id, int) or process_id <= 0:
            msg = "Sandbox returned an invalid process id"
            raise CodeExecutionError(
                msg,
                status_code=status.HTTP_502_BAD_GATEWAY,
                error_code="invalid_process_id",
            )

        self._runtime_handles.setdefault(key, {})[process_id] = handle
        self._runtime_output_offsets[self._runtime_output_key(key, process_id)] = (0, 0)

        return {
            "process_id": process_id,
            "running": True,
            "cwd": runtime_cwd,
            "user": run_user,
        }

    async def read_process_output(
        self,
        *,
        process_id: int,
        user_id: str | None,
        course_id: str | None,
        workspace_id: str | None,
    ) -> dict[str, Any]:
        """Read incremental and full output buffers for a runtime process."""
        key = self._session_key(user_id, course_id)
        sbx = self._get_existing_sandbox_or_raise(key)
        _ = workspace_id

        handle = await self._get_or_connect_runtime_handle(sbx, key, process_id)
        if handle is None:
            msg = f"Runtime process {process_id} was not found"
            raise CodeExecutionError(msg, status_code=status.HTTP_404_NOT_FOUND, error_code="process_not_found")

        running = await self._is_process_running(sbx, process_id)
        if not running and getattr(handle, "exit_code", None) is None:
            try:
                await asyncio.wait_for(handle.wait(), timeout=0.2)
            except CommandExitException:
                pass
            except (OSError, RuntimeError, TimeoutException, SandboxException, TypeError, ValueError):
                logger.debug("Runtime process wait check failed pid=%s", process_id, exc_info=True)

        full_stdout = str(getattr(handle, "stdout", "") or "")
        full_stderr = str(getattr(handle, "stderr", "") or "")
        stdout_offset, stderr_offset = self._runtime_output_offsets.get(self._runtime_output_key(key, process_id), (0, 0))
        safe_stdout_offset = max(0, min(stdout_offset, len(full_stdout)))
        safe_stderr_offset = max(0, min(stderr_offset, len(full_stderr)))
        stdout_delta = full_stdout[safe_stdout_offset:]
        stderr_delta = full_stderr[safe_stderr_offset:]
        self._runtime_output_offsets[self._runtime_output_key(key, process_id)] = (len(full_stdout), len(full_stderr))

        exit_code = getattr(handle, "exit_code", None)
        return {
            "process_id": process_id,
            "running": running,
            "exit_code": exit_code,
            "stdout": stdout_delta,
            "stderr": stderr_delta,
            "stdout_complete": full_stdout,
            "stderr_complete": full_stderr,
        }

    async def send_process_input(
        self,
        *,
        process_id: int,
        input_text: str,
        user_id: str | None,
        course_id: str | None,
        workspace_id: str | None,
    ) -> dict[str, Any]:
        """Send stdin text to a running runtime process."""
        key = self._session_key(user_id, course_id)
        sbx = self._get_existing_sandbox_or_raise(key)
        _ = workspace_id

        handle = await self._get_or_connect_runtime_handle(sbx, key, process_id)
        if handle is None:
            msg = f"Runtime process {process_id} was not found"
            raise CodeExecutionError(msg, status_code=status.HTTP_404_NOT_FOUND, error_code="process_not_found")

        try:
            await sbx.commands.send_stdin(pid=process_id, data=input_text, request_timeout=20)
        except TimeoutException as exc:
            msg = "Sending runtime stdin timed out"
            raise CodeExecutionError(msg, status_code=status.HTTP_504_GATEWAY_TIMEOUT, error_code="timeout") from exc
        except (
            OSError,
            RuntimeError,
            InvalidArgumentException,
            AuthenticationException,
            SandboxException,
        ) as exc:
            running = await self._is_process_running(sbx, process_id)
            if not running:
                msg = f"Runtime process {process_id} is no longer running"
                raise CodeExecutionError(msg, status_code=status.HTTP_409_CONFLICT, error_code="process_not_running") from exc
            msg = f"Failed to send runtime input: {exc}"
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="runtime_input_failed") from exc

        return {
            "process_id": process_id,
            "accepted": True,
            "bytes_sent": len(input_text.encode("utf-8")),
        }

    async def stop_process(
        self,
        *,
        process_id: int,
        user_id: str | None,
        course_id: str | None,
        workspace_id: str | None,
        wait_timeout_seconds: float | None,
    ) -> dict[str, Any]:
        """Stop a runtime process and clean up local tracking state."""
        key = self._session_key(user_id, course_id)
        sbx = self._get_existing_sandbox_or_raise(key)
        _ = workspace_id

        handle = await self._get_or_connect_runtime_handle(sbx, key, process_id)
        if handle is None:
            msg = f"Runtime process {process_id} was not found"
            raise CodeExecutionError(msg, status_code=status.HTTP_404_NOT_FOUND, error_code="process_not_found")

        killed = False
        try:
            killed = await sbx.commands.kill(pid=process_id, request_timeout=20)
        except TimeoutException as exc:
            msg = "Stopping runtime process timed out"
            raise CodeExecutionError(msg, status_code=status.HTTP_504_GATEWAY_TIMEOUT, error_code="timeout") from exc
        except (
            OSError,
            RuntimeError,
            InvalidArgumentException,
            AuthenticationException,
            SandboxException,
        ) as exc:
            msg = f"Failed to stop runtime process: {exc}"
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="runtime_stop_failed") from exc

        if wait_timeout_seconds is not None and wait_timeout_seconds > 0:
            try:
                await asyncio.wait_for(handle.wait(), timeout=wait_timeout_seconds)
            except CommandExitException:
                pass
            except (OSError, RuntimeError, TimeoutException, SandboxException, TypeError, ValueError):
                logger.debug("Runtime process wait-on-stop failed pid=%s", process_id, exc_info=True)

        running = await self._is_process_running(sbx, process_id)
        self._cleanup_runtime_tracking(key, process_id)
        return {
            "process_id": process_id,
            "stopped": not running,
            "killed": bool(killed),
        }

    async def list_runtime_entries(
        self,
        *,
        path: str,
        depth: int,
        user_id: str | None,
        course_id: str | None,
        workspace_id: str | None,
    ) -> dict[str, Any]:
        """List files and directories inside the runtime scope."""
        key = self._session_key(user_id, course_id)
        sbx = await self._get_sandbox(key)

        target_path = self._resolve_runtime_list_path(
            path=path,
            course_id=course_id,
            workspace_id=workspace_id,
        )
        quoted_path = shlex.quote(target_path)
        list_command = f"find {quoted_path} -maxdepth {depth} -mindepth 1 -printf '%y\\t%s\\t%p\\n' | head -n 500"

        try:
            result = await sbx.commands.run(cmd=list_command, timeout=30, request_timeout=45, user="user")
        except TypeError:
            result = await sbx.commands.run(cmd=list_command, timeout=30, request_timeout=45)
        except CommandExitException as exc:
            error_text = getattr(exc, "stderr", None) or str(exc)
            msg = self._command_failure_message(list_command, error_text)
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="list_failed") from exc
        except TimeoutException as exc:
            msg = "Listing runtime entries timed out"
            raise CodeExecutionError(msg, status_code=status.HTTP_504_GATEWAY_TIMEOUT, error_code="timeout") from exc
        except (
            OSError,
            RuntimeError,
            InvalidArgumentException,
            AuthenticationException,
            SandboxException,
        ) as exc:
            msg = f"Failed to list runtime entries: {exc}"
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="runtime_list_failed") from exc

        entries: list[dict[str, Any]] = []
        stdout = str(getattr(result, "stdout", "") or "")
        for raw_line in stdout.splitlines():
            if "\t" not in raw_line:
                continue
            kind, size, item_path = self._parse_runtime_list_line(raw_line)
            entries.append(
                {
                    "type": "dir" if kind == "d" else "file",
                    "size": size,
                    "path": item_path,
                }
            )

        return {
            "path": target_path,
            "depth": depth,
            "entries": entries,
        }

    async def _run_code(self, sbx: Any, source_code: str, language: str) -> Any:
        """Run code in sandbox."""
        return await sbx.run_code(code=source_code, language=language)

    async def _run_code_with_handling(self, sbx: Any, source_code: str, language: str) -> Any:
        try:
            return await self._run_code(sbx, source_code, language)
        except TimeoutException as exc:
            msg = "Execution timed out in the sandbox. Try simplifying the workload or increasing the timeout."
            raise CodeExecutionError(msg, status_code=status.HTTP_504_GATEWAY_TIMEOUT, error_code="timeout") from exc
        except RateLimitException as exc:
            msg = "Sandbox rate limit exceeded. Please wait before retrying your code."
            raise CodeExecutionError(msg, status_code=status.HTTP_429_TOO_MANY_REQUESTS, error_code="rate_limit") from exc
        except InvalidArgumentException as exc:
            msg = "Invalid execution request sent to the sandbox. Check language and inputs."
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_argument") from exc
        except NotEnoughSpaceException as exc:
            msg = "The sandbox ran out of available space while executing the code."
            raise CodeExecutionError(msg, status_code=status.HTTP_507_INSUFFICIENT_STORAGE, error_code="insufficient_storage") from exc
        except AuthenticationException as exc:
            msg = "Sandbox authentication failed. Verify execution credentials."
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="authentication") from exc
        except SandboxException as exc:
            msg = "Sandbox returned an error while running the code."
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="sandbox_error") from exc

    def _extract_result(self, exec_result: Any) -> ExecutionResult:
        """Extract normalized result from E2B Execution object."""
        stdout = self._extract_primary_text(exec_result)
        logs_stdout, logs_stderr = self._extract_logs(exec_result)
        stdout = _append_text(stdout, logs_stdout)
        stderr = logs_stderr

        status, stderr = self._extract_error(exec_result, stderr)
        if status is None and stderr:
            status = "error"

        if not stdout:
            stdout = self._extract_results_stdout(exec_result)

        return ExecutionResult(
            stdout=stdout,
            stderr=stderr,
            status=status,
            time=None,
            memory=None,
        )

    def _extract_primary_text(self, exec_result: Any) -> str | None:
        exec_text = getattr(exec_result, "text", None)
        return exec_text or None

    def _extract_logs(self, exec_result: Any) -> tuple[str | None, str | None]:
        logs = getattr(exec_result, "logs", None)
        if not logs:
            return None, None

        stdout_list = getattr(logs, "stdout", None)
        stderr_list = getattr(logs, "stderr", None)
        stdout = "".join(stdout_list) if stdout_list else None
        stderr = "".join(stderr_list) if stderr_list else None
        return stdout, stderr

    def _extract_error(self, exec_result: Any, stderr: str | None) -> tuple[str | None, str | None]:
        error = getattr(exec_result, "error", None)
        if error is None:
            return None, stderr

        status = "error"
        traceback = getattr(error, "traceback", None)
        if traceback:
            return status, _append_text(stderr, traceback)

        err_text = str(error)
        return status, _append_text(stderr, err_text)

    def _extract_results_stdout(self, exec_result: Any) -> str | None:
        results = getattr(exec_result, "results", None)
        if not results or not isinstance(results, list):
            return None

        last_result = results[-1]
        if hasattr(last_result, "text") and last_result.text:
            return last_result.text

        if hasattr(last_result, "elements") and hasattr(last_result.elements, "elements"):
            elements = last_result.elements.elements
            if isinstance(elements, dict):
                text = elements.get("text/plain")
                if text:
                    return text

        if hasattr(last_result, "data") and isinstance(last_result.data, dict):
            return last_result.data.get("text/plain")
        return None

    def _is_context_restart(self, result: ExecutionResult) -> bool:
        msg = (result.stderr or "") + " " + (result.status or "")
        msg_l = msg.lower()
        return "contextrestarting" in msg_l or "context was restarted" in msg_l or "restarted" in msg_l

    async def _reset_session(self, key: str) -> None:
        _created, sbx = self._sessions.pop(key, (None, None))
        self._setup_done_by_key.pop(key, None)
        if sbx:
            self._runtime_install_locks.pop(self._runtime_lock_key(sbx), None)
            try:
                closer = getattr(sbx, "close", None)
                if callable(closer):
                    await _maybe_await(closer())
                else:
                    acloser = getattr(sbx, "aclose", None)
                    if callable(acloser):
                        await _maybe_await(acloser())
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.exception("Failed to close sandbox during reset key=%s", key)

    def _plan_cache_key(self, course_id: str | None, language: str, source_code: str) -> str:
        """Generate cache key for execution plans."""
        # Use first 50 chars to capture import/structure patterns
        code_prefix = source_code[:50].strip()
        code_hash = hashlib.sha256(code_prefix.encode()).hexdigest()[:16]
        return f"{course_id or '_'}:{language.lower()}:{code_hash}"

    async def _run_course_setup(self, sbx: Any, *, setup_key: str, course_id: str, setup_commands: list[str]) -> None:
        """Run course setup commands once per sandbox."""
        logger.info("Running course setup course_id=%s key=%s commands=%d", course_id, setup_key, len(setup_commands))
        had_setup_failures = False
        for cmd in setup_commands:
            run_user = self._setup_command_run_user(cmd)
            try:
                result = await sbx.commands.run(cmd, user=run_user)
                if result.exit_code != 0:
                    had_setup_failures = True
                    logger.warning(
                        "sandbox.setup_command.failed",
                        extra={"command_sig": self._command_signature(cmd), "exit_code": result.exit_code},
                    )
            except (
                OSError,
                RuntimeError,
                TimeoutException,
                RateLimitException,
                InvalidArgumentException,
                NotEnoughSpaceException,
                AuthenticationException,
                SandboxException,
                CommandExitException,
            ):
                had_setup_failures = True
                logger.exception("sandbox.setup_command.error", extra={"command_sig": self._command_signature(cmd)})

        if had_setup_failures:
            logger.warning("sandbox.setup.incomplete", extra={"course_id": course_id, "key": setup_key})
            return

        self._setup_done_by_key[setup_key] = True

    async def _persist_normalized_setup_commands(self, course_id: str, setup_commands: list[str]) -> None:
        """Persist normalized setup commands for the course to avoid repeated runtime rewrites."""
        try:
            course_uuid = uuid.UUID(course_id)
        except ValueError:
            logger.warning("Skipping setup command persistence for invalid course_id=%s", course_id)
            return

        payload = json.dumps(setup_commands)
        try:
            await self._session.execute(
                update(Course)
                .where(Course.id == course_uuid)
                .values(setup_commands=payload, updated_at=datetime.now(UTC))
            )
            await self._session.commit()
            logger.info("Persisted normalized setup commands for course_id=%s", course_id)
        except SQLAlchemyError:
            await self._session.rollback()
            logger.exception("Failed to persist normalized setup commands for course_id=%s", course_id)

    def _setup_command_run_user(self, command: str) -> str | None:
        """Select command user for setup steps that require elevated permissions."""
        for segment in command.split("&&"):
            tokens = self._safe_split_shell_command(segment)
            if not tokens:
                continue
            if tokens[0] in {"apt", "apt-get"}:
                return "root"
            if len(tokens) >= 2 and tokens[0] == "sudo" and tokens[1] in {"apt", "apt-get"}:
                return "root"
        return None

    @staticmethod
    def _safe_split_shell_command(command: str) -> list[str]:
        try:
            return shlex.split(command)
        except ValueError:
            return []

    async def _ensure_runtime(self, sbx: Any, language: str) -> None:
        """Install language runtime for fast-path execution when missing."""
        installers = FAST_PATH_INSTALLERS.get(language)
        if not installers:
            return

        install_lock = self._runtime_install_locks.setdefault(self._runtime_lock_key(sbx), asyncio.Lock())
        async with install_lock:
            sentinel_path = f"{self._language_sentinel_prefix}{language}"
            try:
                await sbx.files.read(sentinel_path)
                return
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.debug("Runtime sentinel missing for %s, proceeding with provisioning", language, exc_info=True)

            runtime_binary = "rustc" if language == "rust" else language
            try:
                result = await sbx.commands.run(f"command -v {shlex.quote(runtime_binary)}", timeout=60)
                if getattr(result, "exit_code", None) == 0:
                    await sbx.files.write(sentinel_path, "present")
                    return
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.debug("Runtime presence check failed for %s", language, exc_info=True)

            logger.info("Installing runtime lang=%s commands=%s", language, installers)
            stdout_chunks: list[str] = []
            stderr_chunks: list[str] = []
            await self._run_command_list(
                sbx,
                installers,
                {},
                stdout_chunks,
                stderr_chunks,
                user="root",
            )
            await sbx.files.write(sentinel_path, "installed")

    async def _fast_path_execute(
        self, sbx: Any, language: str, source_code: str, _stdin: str | None
    ) -> ExecutionResult:
        """Execute code using fast-path template (no AI)."""
        template = FAST_PATH_TEMPLATES[language]
        filepath = f"{HOME_USER_DIR}/{template['file']}"

        # Write code to file
        await sbx.files.write(path=filepath, data=source_code)

        # Execute command
        cmd = template["cmd"]
        result = await sbx.commands.run(cmd, envs={"PYTHONUNBUFFERED": "1"} if language == "python" else {})

        return ExecutionResult(
            stdout=result.stdout or None,
            stderr=result.stderr or None,
            status="success" if result.exit_code == 0 else "error",
            time=None,
            memory=None,
        )

    async def _plan_and_execute_with_ai(
        self,
        *,
        sbx: Any,
        source_code: str,
        language: str,
        stdin: str | None,
        user_id: str | None,
        lesson_id: str | None,
        scope_key: str,
        cache_key: str | None = None,
        workspace_entry_file: str | None = None,
        workspace_root: str | None = None,
        workspace_files: Sequence[str] | None = None,
        workspace_identifier: str | None = None,
        is_workspace_mode: bool = False,
    ) -> ExecutionResult:
        sandbox_state = await self._gather_sandbox_state(sbx)
        sandbox_context = self._build_sandbox_tool_context(sbx, scope_key)
        plan = await self._ai_service.generate_execution_plan(
            language=language,
            source_code=source_code,
            stderr=None,
            stdin=stdin,
            sandbox_state=sandbox_state,
            user_id=user_id,
            workspace_entry=workspace_entry_file,
            workspace_root=workspace_root,
            workspace_files=list(workspace_files) if workspace_files else None,
            workspace_id=workspace_identifier,
            sandbox_context=sandbox_context,
        )

        # Cache the plan for future use
        if cache_key:
            self._plan_cache[cache_key] = plan
            logger.debug("Cached execution plan cache_key=%s", cache_key)

        return await self._apply_execution_plan(
            sbx=sbx,
            plan=plan,
            source_code=source_code,
            language=language,
            lesson_id=lesson_id,
            is_workspace_mode=is_workspace_mode,
            workspace_entry_file=workspace_entry_file,
            workspace_root=workspace_root,
        )

    async def _gather_sandbox_state(self, sbx: Any) -> dict[str, Any]:
        state: dict[str, Any] = {}
        try:
            await sbx.files.read(self._apt_sentinel)
            state["apt_updated"] = True
        except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
            state["apt_updated"] = False
        return state

    def _build_sandbox_tool_context(self, sbx: Any, scope_key: str) -> SandboxToolContext:
        async def run_command(
            command: str,
            cwd: str | None,
            user: str | None,
            timeout_seconds: int | None,
        ) -> dict[str, Any]:
            timeout = timeout_seconds or 120
            request_timeout = max(timeout + 30, 60)
            run_user = user or "user"
            try:
                result = await sbx.commands.run(
                    cmd=command,
                    timeout=timeout,
                    request_timeout=request_timeout,
                    user=run_user,
                    cwd=cwd,
                )
            except TypeError:
                result = await sbx.commands.run(
                    cmd=command,
                    timeout=timeout,
                    request_timeout=request_timeout,
                    user=run_user,
                )
            return {
                "exit_code": getattr(result, "exit_code", None),
                "stdout": getattr(result, "stdout", "") or "",
                "stderr": getattr(result, "stderr", "") or "",
            }

        async def read_file(path: str) -> str:
            content = await sbx.files.read(path)
            return str(content)

        async def write_file(path: str, content: str) -> dict[str, Any]:
            await sbx.files.write(path=path, data=content)
            return {"written": True}

        async def list_dir(path: str, depth: int) -> list[dict[str, Any]]:
            normalized_path = path.strip() or "."
            quoted_path = shlex.quote(normalized_path)
            command = (
                f"find {quoted_path} -maxdepth {depth} -mindepth 1 -printf '%y\\t%p\\n' "
                "| head -n 200"
            )
            run_result = await run_command(command, None, "user", 30)
            stdout = str(run_result.get("stdout", ""))
            entries: list[dict[str, Any]] = []
            for raw_line in stdout.splitlines():
                if "\t" not in raw_line:
                    continue
                raw_kind, raw_path = raw_line.split("\t", 1)
                entry_type = "dir" if raw_kind == "d" else "file"
                entries.append({"path": raw_path, "type": entry_type})
            return entries

        async def reset() -> dict[str, Any]:
            await run_command(f"rm -rf {WORKSPACES_DIR}/*", None, "user", 30)
            return {"status": "reset", "scope_key": scope_key}

        return SandboxToolContext(
            scope_key=scope_key,
            run_command=run_command,
            read_file=read_file,
            write_file=write_file,
            list_dir=list_dir,
            reset=reset,
        )

    async def _apply_execution_plan(
        self,
        *,
        sbx: Any,
        plan: Any,
        source_code: str,
        language: str,
        lesson_id: str | None,
        is_workspace_mode: bool = False,
        workspace_entry_file: str | None = None,
        workspace_root: str | None = None,
    ) -> ExecutionResult:
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        envs = dict(getattr(plan, "environment", {}) or {})

        await self._materialize_plan_files(sbx, plan)
        source_code = await self._apply_plan_actions(
            sbx=sbx,
            plan=plan,
            envs=envs,
            stdout_chunks=stdout_chunks,
            stderr_chunks=stderr_chunks,
            source_code=source_code,
            lesson_id=lesson_id,
        )

        await self._run_command_list(sbx, plan.setup_commands, envs, stdout_chunks, stderr_chunks)
        await self._run_command_list(sbx, plan.install_commands, envs, stdout_chunks, stderr_chunks)

        if plan.run_commands:
            await self._run_command_list(sbx, plan.run_commands, envs, stdout_chunks, stderr_chunks)
            return self._finalize_command_run(stdout_chunks=stdout_chunks, stderr_chunks=stderr_chunks)

        return await self._execute_when_no_run_commands(
            sbx=sbx,
            source_code=source_code,
            language=language,
            envs=envs,
            stdout_chunks=stdout_chunks,
            stderr_chunks=stderr_chunks,
            is_workspace_mode=is_workspace_mode,
            workspace_entry_file=workspace_entry_file,
            workspace_root=workspace_root,
        )

    async def _materialize_plan_files(self, sbx: Any, plan: Any) -> None:
        if not getattr(plan, "files", None):
            return

        for file_entry in plan.files:
            try:
                await sbx.files.write(path=file_entry.path, data=file_entry.content)
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.exception("Failed to write file %s", file_entry.path)
                raise

    async def _apply_plan_actions(
        self,
        *,
        sbx: Any,
        plan: Any,
        envs: dict[str, str],
        stdout_chunks: list[str],
        stderr_chunks: list[str],
        source_code: str,
        lesson_id: str | None,
    ) -> str:
        if not getattr(plan, "actions", None):
            return source_code

        return await self._apply_actions(
            sbx=sbx,
            actions=list(plan.actions),
            envs=envs,
            stdout_chunks=stdout_chunks,
            stderr_chunks=stderr_chunks,
            source_code=source_code,
            lesson_id=lesson_id,
        )

    async def _execute_when_no_run_commands(
        self,
        *,
        sbx: Any,
        source_code: str,
        language: str,
        envs: dict[str, str],
        stdout_chunks: list[str],
        stderr_chunks: list[str],
        is_workspace_mode: bool,
        workspace_entry_file: str | None,
        workspace_root: str | None,
    ) -> ExecutionResult:
        norm_lang = language.lower().strip()

        workspace_default = (
            self._default_workspace_run(
                language=norm_lang,
                workspace_entry_file=workspace_entry_file,
                workspace_root=workspace_root,
            )
            if is_workspace_mode and workspace_entry_file
            else None
        )
        if workspace_default:
            cwd, cmd = workspace_default
            await self._ensure_runtime(sbx, norm_lang)
            await self._run_command_list(sbx, [cmd], envs, stdout_chunks, stderr_chunks, cwd=cwd)
            return self._finalize_command_run(stdout_chunks=stdout_chunks, stderr_chunks=stderr_chunks)

        if norm_lang in FAST_PATH_TEMPLATES:
            await self._ensure_runtime(sbx, norm_lang)
            return await self._fast_path_execute(sbx, norm_lang, source_code, None)

        exec_result = await self._run_code_with_handling(sbx, source_code, language)
        return self._extract_result(exec_result)

    def _finalize_command_run(self, *, stdout_chunks: list[str], stderr_chunks: list[str]) -> ExecutionResult:
        stdout = "\n".join(chunk for chunk in stdout_chunks if chunk)
        stderr = "\n".join(chunk for chunk in stderr_chunks if chunk)

        status = "error" if stderr and not stdout else None
        return ExecutionResult(
            stdout=stdout or None,
            stderr=stderr or None,
            status=status,
            time=None,
            memory=None,
        )

    def _default_workspace_run(
        self,
        *,
        language: str,
        workspace_entry_file: str,
        workspace_root: str | None,
    ) -> tuple[str, str] | None:
        root = workspace_root.rstrip("/") if workspace_root else None
        cwd = root or posixpath.dirname(workspace_entry_file) or "."
        entry_rel = workspace_entry_file
        if root and workspace_entry_file.startswith(root + "/"):
            entry_rel = workspace_entry_file[len(root) + 1 :]

        entry_q = shlex.quote(entry_rel)

        run_templates: dict[str, str] = {
            "python": "python3 {entry}",
            "javascript": "node {entry}",
            "typescript": "npx tsx {entry}",
            "go": "go run {entry}",
            "ruby": "ruby {entry}",
            "php": "php {entry}",
            "r": "Rscript {entry}",
            "lua": "lua {entry}",
        }
        compile_templates: dict[str, str] = {
            "rust": "rustc {entry} -o main && ./main",
            "c": "gcc {entry} -o main && ./main",
            "cpp": "g++ {entry} -o main && ./main",
        }

        template = run_templates.get(language) or compile_templates.get(language)
        if not template:
            return None

        return cwd, template.format(entry=entry_q)

    async def _try_workspace_fast_path(  # noqa: PLR0911
        self,
        *,
        sbx: Any,
        language: str,
        workspace_entry_file: str | None,
        workspace_root: str | None,
    ) -> ExecutionResult | None:
        if workspace_entry_file is None:
            return None

        workspace_default = self._default_workspace_run(
            language=language,
            workspace_entry_file=workspace_entry_file,
            workspace_root=workspace_root,
        )
        if workspace_default is None:
            return None

        cwd, command = workspace_default
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []
        try:
            await self._ensure_runtime(sbx, language)
            await self._run_command_list(sbx, [command], {}, stdout_chunks, stderr_chunks, cwd=cwd)
            return self._finalize_command_run(stdout_chunks=stdout_chunks, stderr_chunks=stderr_chunks)
        except CodeExecutionError:
            stderr_text = "\n".join(chunk for chunk in stderr_chunks if chunk)
            dependency_commands = self._infer_workspace_dependency_commands(language=language, stderr_text=stderr_text)
            if not dependency_commands:
                return None

            try:
                await self._run_command_list(sbx, dependency_commands, {}, stdout_chunks, stderr_chunks, cwd=cwd)
                await self._run_command_list(sbx, [command], {}, stdout_chunks, stderr_chunks, cwd=cwd)
                return self._finalize_command_run(stdout_chunks=stdout_chunks, stderr_chunks=stderr_chunks)
            except CodeExecutionError:
                return None
        except (
            OSError,
            RuntimeError,
            TimeoutException,
            RateLimitException,
            InvalidArgumentException,
            NotEnoughSpaceException,
            AuthenticationException,
            SandboxException,
            CommandExitException,
        ):
            return None

    def _infer_workspace_dependency_commands(self, *, language: str, stderr_text: str) -> list[str]:
        if not stderr_text:
            return []

        if language == "python":
            module_name = self._extract_missing_python_module(stderr_text)
            if module_name:
                return [f"python3 -m pip install {shlex.quote(module_name)}"]

        if language in {"javascript", "typescript"}:
            package_name = self._extract_missing_node_module(stderr_text)
            if package_name:
                return [f"npm install {shlex.quote(package_name)}"]

        return []

    def _extract_missing_python_module(self, stderr_text: str) -> str | None:
        match = re.search(r"No module named ['\"]([^'\"]+)['\"]", stderr_text)
        if match is None:
            return None
        module_name = match.group(1).strip().split(".")[0]
        if not module_name:
            return None
        if re.fullmatch(r"[A-Za-z0-9._-]+", module_name) is None:
            return None
        return module_name

    def _extract_missing_node_module(self, stderr_text: str) -> str | None:
        match = re.search(r"Cannot find module ['\"]([^'\"]+)['\"]", stderr_text)
        if match is None:
            return None
        package_name = match.group(1).strip()
        if not package_name or package_name.startswith("."):
            return None
        if re.fullmatch(r"[A-Za-z0-9@._/-]+", package_name) is None:
            return None
        return package_name

    def _summarize_stderr(self, stderr_text: str | None) -> str | None:
        if not stderr_text:
            return None

        first_line = ""
        for raw_line in str(stderr_text).splitlines():
            candidate = raw_line.strip()
            if candidate:
                first_line = candidate
                break

        if not first_line:
            return None

        if len(first_line) > 200:
            return f"{first_line[:197]}..."
        return first_line

    def _command_failure_message(self, command: str, stderr_text: str | None) -> str:
        base_message = f"Command failed: {command}"
        diagnostic = self._summarize_stderr(stderr_text)
        if diagnostic is None:
            return base_message
        return f"{base_message}. stderr: {diagnostic}"

    def _command_exception_message(self, command: str, stderr_text: str | None, error: Exception) -> str:
        base_message = f"Command execution failed: {command}"
        diagnostic = self._summarize_stderr(stderr_text) or self._summarize_stderr(str(error))
        if diagnostic is None:
            return base_message
        return f"{base_message}. detail: {diagnostic}"

    @staticmethod
    def _command_signature(command: str) -> str:
        return hashlib.sha256(command.encode("utf-8")).hexdigest()[:12]

    async def _run_command_list(
        self,
        sbx: Any,
        commands: list[str],
        envs: dict[str, str],
        stdout_chunks: list[str],
        stderr_chunks: list[str],
        *,
        user: str | None = None,
        cwd: str | None = None,
    ) -> None:
        if not commands:
            return

        for command in commands:
            normalized_command = command.strip()
            if not normalized_command:
                continue
            run_user = user or "user"
            command_sig = self._command_signature(normalized_command)
            logger.debug("sandbox.command.started", extra={"user": run_user, "command_sig": command_sig})
            try:
                try:
                    result = await sbx.commands.run(
                        cmd=normalized_command,
                        envs=envs or None,
                        timeout=240,
                        request_timeout=300,
                        user=run_user,
                        cwd=cwd,
                    )
                except TypeError:
                    result = await sbx.commands.run(
                        cmd=normalized_command,
                        envs=envs or None,
                        timeout=240,
                        request_timeout=300,
                        user=run_user,
                    )
            except CommandExitException as exc:
                stderr_text = getattr(exc, "stderr", "")
                if stderr_text:
                    stderr_chunks.append(stderr_text)
                error_message = self._command_failure_message(normalized_command, stderr_text)
                raise CodeExecutionError(
                    error_message,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error_code="command_failed",
                ) from exc
            except (
                OSError,
                RuntimeError,
                TimeoutException,
                RateLimitException,
                InvalidArgumentException,
                NotEnoughSpaceException,
                AuthenticationException,
                SandboxException,
                TypeError,
            ) as exc:
                logger.exception("sandbox.command.error", extra={"command_sig": command_sig})
                stderr_text = getattr(exc, "stderr", "")
                if stderr_text:
                    stderr_chunks.append(stderr_text)
                error_message = self._command_exception_message(normalized_command, stderr_text, exc)
                raise CodeExecutionError(
                    error_message,
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    error_code="command_error",
                ) from exc

            if getattr(result, "stdout", None):
                stdout_chunks.append(result.stdout)
            if getattr(result, "stderr", None):
                stderr_chunks.append(result.stderr)

            if APT_GET_UPDATE_COMMAND in normalized_command:
                try:
                    await sbx.files.write(self._apt_sentinel, "updated")
                except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                    logger.exception("Failed to record apt sentinel")

    async def _apply_actions(
        self,
        *,
        sbx: Any,
        actions: list[PlanAction],
        envs: dict[str, str],
        stdout_chunks: list[str],
        stderr_chunks: list[str],
        source_code: str,
        lesson_id: str | None,
    ) -> str:
        updated_source = source_code
        for action in actions:
            if action.type == "command":
                command = action.command or ""
                if not command.strip():
                    logger.debug("Skipping empty command action")
                    continue
                await self._run_command_list(
                    sbx,
                    [command],
                    envs,
                    stdout_chunks,
                    stderr_chunks,
                    user=action.user,
                )
                continue

            updated_source = await self._apply_patch_action(
                sbx=sbx,
                action=action,
                current_source=updated_source,
                lesson_id=lesson_id,
            )

        return updated_source

    async def _apply_patch_action(
        self,
        *,
        sbx: Any,
        action: PlanAction,
        current_source: str,
        lesson_id: str | None,
    ) -> str:
        if not action.replacement:
            logger.warning("Patch action missing replacement text path=%s", action.path)
            return current_source

        path = action.path
        replacement = action.replacement
        original = action.original or ""

        if path:
            try:
                existing = await sbx.files.read(path)
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.debug("Patch target missing, creating file path=%s", path, exc_info=True)
                existing = None

            if existing and original and original in existing:
                new_content = existing.replace(original, replacement, 1)
            else:
                new_content = replacement

            try:
                await sbx.files.write(path=path, data=new_content)
                logger.info("Applied sandbox patch path=%s", path)
            except (OSError, RuntimeError, TimeoutException, SandboxException, CommandExitException):
                logger.exception("Failed to write patched file path=%s", path)
                raise
        else:
            logger.warning("Patch action missing path; skipping file write")

        updated_source = self._replace_source_with_patch(current_source, original, replacement)

        if lesson_id:
            await self._persist_lesson_patch(lesson_id, original, replacement)

        return updated_source

    def _replace_source_with_patch(self, source_code: str, original: str, replacement: str) -> str:
        if original and original in source_code:
            return source_code.replace(original, replacement, 1)
        if not original:
            return replacement
        return source_code

    async def _persist_lesson_patch(self, lesson_id: str, original: str, replacement: str) -> None:
        try:
            lesson_uuid = uuid.UUID(lesson_id)
        except (ValueError, TypeError):
            logger.debug("Invalid lesson_id for patch persistence lesson_id=%s", lesson_id)
            return

        try:
            lesson = await self._session.get(Lesson, lesson_uuid)
            if lesson is None:
                logger.debug("Lesson not found for patch persistence lesson_id=%s", lesson_id)
                return

            existing_content = lesson.content or ""
            updated_content = self._replace_source_with_patch(existing_content, original, replacement)

            if existing_content == updated_content:
                if original:
                    logger.debug("Original snippet not found in lesson content lesson_id=%s", lesson_id)
                return

            lesson.content = updated_content
            await self._session.flush()
            logger.info("Persisted AI patch to lesson lesson_id=%s", lesson_id)
        except SQLAlchemyError:
            logger.exception("Failed to persist patch for lesson lesson_id=%s", lesson_id)

    async def _prepare_workspace(
        self,
        *,
        sbx: Any,
        files: Sequence[WorkspaceFile],
        workspace_id: str | None,
        course_id: str | None,
        lesson_id: str | None,
        entry_file: str | None,
    ) -> dict[str, Any]:
        file_list = list(files)
        if not file_list:
            msg = "Workspace execution requires at least one file"
            raise ValueError(msg)

        workspace_dir = self._resolve_workspace_root(workspace_id, course_id, lesson_id)
        await self._reset_workspace_directory(sbx, workspace_dir)

        directories: set[str] = set()
        manifest: list[str] = []
        writes: list[tuple[str, str]] = []

        for file in file_list:
            resolved_path, _relative_path = self._resolve_workspace_file_path(workspace_dir, file.path)
            manifest.append(resolved_path)
            parent_dir = posixpath.dirname(resolved_path)
            if parent_dir and parent_dir.startswith(workspace_dir) and parent_dir != workspace_dir:
                directories.add(parent_dir)
            writes.append((resolved_path, file.content))

        if directories:
            await self._ensure_directories(sbx, directories)

        for resolved_path, contents in writes:
            await sbx.files.write(path=resolved_path, data=contents)

        resolved_entry, _ = self._resolve_workspace_file_path(workspace_dir, entry_file or file_list[0].path)
        identifier = workspace_id or "workspace"

        return {
            "entry_file": resolved_entry,
            "workspace_dir": workspace_dir,
            "manifest": manifest,
            "identifier": identifier,
        }

    def _resolve_workspace_root(self, workspace_id: str | None, course_id: str | None, lesson_id: str | None) -> str:
        safe_id = self._sanitize_workspace_id(workspace_id)
        scope = f"{course_id or '_'}:{lesson_id or '_'}:{workspace_id or safe_id}"
        digest = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:10]
        return posixpath.join(self._workspace_root, f"{safe_id}-{digest}")

    def _sanitize_workspace_id(self, workspace_id: str | None) -> str:
        base = (workspace_id or "workspace").strip().lower()
        filtered = "".join(ch if ch.isalnum() or ch in ("-", "_") else "-" for ch in base)
        sanitized = filtered.strip("-_") or "workspace"
        return sanitized[:48]

    async def _reset_workspace_directory(self, sbx: Any, workspace_dir: str) -> None:
        if not workspace_dir.startswith(self._workspace_root):
            msg = "Workspace directory outside sandbox root"
            raise ValueError(msg)
        root_quoted = shlex.quote(self._workspace_root)
        await sbx.commands.run(f"mkdir -p {root_quoted}")
        quoted = shlex.quote(workspace_dir)
        await sbx.commands.run(f"rm -rf {quoted} && mkdir -p {quoted}")

    async def _ensure_directories(self, sbx: Any, directories: set[str]) -> None:
        for directory in sorted(directories):
            if not directory.startswith(self._workspace_root):
                continue
            quoted = shlex.quote(directory)
            await sbx.commands.run(f"mkdir -p {quoted}")

    def _resolve_workspace_file_path(self, workspace_dir: str, raw_path: str) -> tuple[str, str]:
        relative = self._normalize_workspace_relative_path(raw_path)
        return posixpath.join(workspace_dir, relative), relative

    def _normalize_workspace_relative_path(self, raw_path: str) -> str:
        candidate = (raw_path or "").replace("\\", "/").strip()
        candidate = candidate.lstrip("/")
        normalized = posixpath.normpath(candidate)
        if normalized in ("", ".", "..") or normalized.startswith("../"):
            msg = f"Invalid workspace file path: {raw_path}"
            raise ValueError(msg)
        return normalized

    def _normalize_runtime_env(self, env: dict[str, str] | None) -> dict[str, str]:
        if not env:
            return {}
        normalized: dict[str, str] = {}
        for key, value in env.items():
            name = str(key).strip()
            if not name:
                continue
            normalized[name] = str(value)
        return normalized

    def _runtime_output_key(self, scope_key: str, process_id: int) -> str:
        return f"{scope_key}:{process_id}"

    def _runtime_lock_key(self, sbx: Any) -> str:
        sandbox_id = getattr(sbx, "sandbox_id", None)
        if isinstance(sandbox_id, str) and sandbox_id.strip():
            return sandbox_id
        return str(id(sbx))

    def _cleanup_runtime_tracking(self, scope_key: str, process_id: int) -> None:
        process_handles = self._runtime_handles.get(scope_key)
        if process_handles is not None:
            process_handles.pop(process_id, None)
            if not process_handles:
                self._runtime_handles.pop(scope_key, None)
        self._runtime_output_offsets.pop(self._runtime_output_key(scope_key, process_id), None)

    async def _get_or_connect_runtime_handle(self, sbx: Any, scope_key: str, process_id: int) -> Any | None:
        known = self._runtime_handles.get(scope_key, {}).get(process_id)
        if known is not None:
            return known

        try:
            handle = await sbx.commands.connect(pid=process_id, timeout=5, request_timeout=15)
        except (
            OSError,
            RuntimeError,
            TimeoutException,
            InvalidArgumentException,
            AuthenticationException,
            SandboxException,
            TypeError,
            ValueError,
        ):
            return None

        self._runtime_handles.setdefault(scope_key, {})[process_id] = handle
        self._runtime_output_offsets.setdefault(self._runtime_output_key(scope_key, process_id), (0, 0))
        return handle

    async def _is_process_running(self, sbx: Any, process_id: int) -> bool:
        try:
            processes = await sbx.commands.list(request_timeout=20)
        except TypeError:
            processes = await sbx.commands.list()
        except (
            OSError,
            RuntimeError,
            TimeoutException,
            InvalidArgumentException,
            AuthenticationException,
            SandboxException,
        ):
            return False
        return any(getattr(process, "pid", None) == process_id for process in processes)

    def _get_existing_sandbox_or_raise(self, key: str) -> Any:
        record = self._sessions.get(key)
        if record is None:
            msg = "Runtime sandbox session was not found"
            raise CodeExecutionError(msg, status_code=status.HTTP_404_NOT_FOUND, error_code="runtime_session_not_found")
        return record[1]

    def _resolve_runtime_working_directory(self, *, course_id: str | None, workspace_id: str | None, cwd: str | None) -> str | None:
        workspace_root = self._resolve_workspace_root(workspace_id, course_id, None) if workspace_id else None
        normalized_cwd = (cwd or "").strip()
        if not normalized_cwd:
            return workspace_root

        if workspace_root:
            if normalized_cwd.startswith("/"):
                resolved = posixpath.normpath(normalized_cwd)
                if resolved == workspace_root or resolved.startswith(f"{workspace_root}/"):
                    return resolved
                msg = "Runtime cwd must stay inside the workspace root"
                raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_cwd")

            relative = self._normalize_workspace_relative_path(normalized_cwd)
            return posixpath.join(workspace_root, relative)

        if normalized_cwd.startswith("/"):
            resolved = posixpath.normpath(normalized_cwd)
        else:
            resolved = posixpath.normpath(posixpath.join(HOME_USER_DIR, normalized_cwd))

        if resolved == HOME_USER_DIR or resolved.startswith(f"{HOME_USER_DIR}/"):
            return resolved
        msg = f"Runtime cwd must stay inside {HOME_USER_DIR}"
        raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_cwd")

    def _resolve_runtime_list_path(self, *, path: str, course_id: str | None, workspace_id: str | None) -> str:
        normalized_path = (path or ".").strip()
        workspace_root = self._resolve_workspace_root(workspace_id, course_id, None) if workspace_id else None
        if workspace_root:
            if normalized_path in {"", "."}:
                return workspace_root
            if normalized_path.startswith("/"):
                resolved = posixpath.normpath(normalized_path)
                if resolved == workspace_root or resolved.startswith(f"{workspace_root}/"):
                    return resolved
                msg = "Runtime list path must stay inside the workspace root"
                raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_path")
            relative = self._normalize_workspace_relative_path(normalized_path)
            return posixpath.join(workspace_root, relative)

        if normalized_path.startswith("/"):
            resolved = posixpath.normpath(normalized_path)
        else:
            resolved = posixpath.normpath(posixpath.join(HOME_USER_DIR, normalized_path))

        if resolved == HOME_USER_DIR or resolved.startswith(f"{HOME_USER_DIR}/"):
            return resolved
        msg = f"Runtime list path must stay inside {HOME_USER_DIR}"
        raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_path")

    async def _ensure_runtime_directory_exists(self, sbx: Any, directory_path: str) -> None:
        if not (directory_path == HOME_USER_DIR or directory_path.startswith(f"{HOME_USER_DIR}/")):
            msg = f"Runtime cwd must stay inside {HOME_USER_DIR}"
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="invalid_cwd")

        quoted = shlex.quote(directory_path)
        mkdir_command = f"mkdir -p {quoted}"
        try:
            try:
                await sbx.commands.run(cmd=mkdir_command, timeout=30, request_timeout=45, user="user")
            except TypeError:
                await sbx.commands.run(cmd=mkdir_command, timeout=30, request_timeout=45)
        except CommandExitException as exc:
            error_text = getattr(exc, "stderr", None) or str(exc)
            msg = self._command_failure_message(mkdir_command, error_text)
            raise CodeExecutionError(msg, status_code=status.HTTP_400_BAD_REQUEST, error_code="mkdir_failed") from exc
        except TimeoutException as exc:
            msg = "Preparing runtime working directory timed out"
            raise CodeExecutionError(msg, status_code=status.HTTP_504_GATEWAY_TIMEOUT, error_code="timeout") from exc
        except (
            OSError,
            RuntimeError,
            InvalidArgumentException,
            AuthenticationException,
            SandboxException,
        ) as exc:
            msg = f"Failed to prepare runtime working directory: {exc}"
            raise CodeExecutionError(msg, status_code=status.HTTP_502_BAD_GATEWAY, error_code="mkdir_failed") from exc

    def _parse_runtime_list_line(self, raw_line: str) -> tuple[str, int, str]:
        parts = raw_line.split("\t", 2)
        if len(parts) != 3:
            return "f", 0, raw_line
        raw_kind, raw_size, raw_path = parts
        try:
            size = int(raw_size)
        except (TypeError, ValueError):
            size = 0
        kind = raw_kind if raw_kind in {"d", "f"} else "f"
        return kind, size, raw_path


async def _maybe_await(value: Any) -> Any:
    if asyncio.iscoroutine(value):
        return await value
    return value


def _append_text(base: str | None, addition: str | None) -> str | None:
    if not addition:
        return base
    if not base:
        return addition
    return f"{base}\n{addition}".strip()
