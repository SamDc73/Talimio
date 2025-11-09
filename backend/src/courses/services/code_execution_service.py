"""AI-powered code execution service using E2B Code Interpreter sandboxes.

Fully autonomous execution with fast-path optimization:
- Fast-path: Common languages execute instantly via templates (<50ms)
- Cached plans: Previously seen patterns reuse cached execution plans (<100ms)
- AI fallback: Exotic languages/errors trigger AI planner (2s)

Sandboxes are reused per user+course with configurable TTL for compute efficiency.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from src.ai.models import PlanAction
from src.ai.service import get_ai_service
from src.courses.models import Lesson
from src.database.session import async_session_maker


# Prefer AsyncSandbox; fall back if package layout differs
try:  # e2b-code-interpreter >= 2.x
    from e2b_code_interpreter import AsyncSandbox  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - version differences
    AsyncSandbox = None  # type: ignore[assignment]

try:  # pragma: no cover - available when SDK is installed
    from e2b.exceptions import (  # type: ignore[import-untyped]
        AuthenticationException,
        InvalidArgumentException,
        NotEnoughSpaceException,
        RateLimitException,
        SandboxException,
        TimeoutException,
    )
    from e2b.sandbox.commands.command_handle import (  # type: ignore[import-untyped]
        CommandExitException,
    )
except Exception:  # pragma: no cover - fallback when the SDK structure changes
    AuthenticationException = InvalidArgumentException = NotEnoughSpaceException = RateLimitException = TimeoutException = SandboxException = Exception  # type: ignore[assignment]
    CommandExitException = SandboxException  # type: ignore[assignment]

# Trim noisy SDK logs by default; configurable via env
E2B_SDK_LOG_LEVEL = os.getenv("E2B_SDK_LOG_LEVEL", "WARNING").upper()
try:
    _e2b_level = getattr(logging, E2B_SDK_LOG_LEVEL, logging.WARNING)
except Exception:
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
        "apt-get update",
        (
            "DEBIAN_FRONTEND=noninteractive DEBCONF_NOWARNINGS=yes "
            "apt-get install -y --no-install-recommends golang-go"
        ),
    ],
}


class CodeExecutionService:
    """AI-powered E2B execution service - handles any language autonomously."""

    # In-memory session cache: key -> (created_time, sandbox)
    _sessions: dict[str, tuple[float, Any]] = {}
    # In-memory plan cache: cache_key -> ExecutionPlan (simple dict, no Redis)
    _plan_cache: dict[str, Any] = {}
    # Course setup tracking: course_id -> bool
    _course_setup_done: dict[str, bool] = {}

    def __init__(self) -> None:
        ttl = os.getenv("E2B_SANDBOX_TTL", "600")
        try:
            self.sandbox_ttl = max(60, int(ttl))
        except ValueError:
            self.sandbox_ttl = 600
        self._ai_service = get_ai_service()
        self._apt_sentinel = "/home/user/.talimio_apt_updated"
        self._language_sentinel_prefix = "/home/user/.talimio_lang_"

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
                # Best effort async close
                closer = getattr(sbx, "close", None)
                if callable(closer):
                    await _maybe_await(closer())
                else:
                    acloser = getattr(sbx, "aclose", None)
                    if callable(acloser):
                        await _maybe_await(acloser())
            except Exception:
                logging.exception("Failed to close sandbox for key %s", k)

        # Reuse if present
        if key in self._sessions:
            sbx = self._sessions[key][1]
            logging.debug("Reusing E2B sandbox for key=%s", key)
            return sbx

        if AsyncSandbox is None:
            msg = "e2b-code-interpreter AsyncSandbox not available"
            raise RuntimeError(msg)

        # Create fresh sandbox
        # We allow internet access to enable on-demand installs later if desired.
        logging.info("Creating new E2B sandbox key=%s ttl=%s", key, self.sandbox_ttl)
        sbx = await AsyncSandbox.create(timeout=self.sandbox_ttl)
        self._sessions[key] = (now, sbx)
        return sbx

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

        # Run course setup commands once per sandbox
        if course_id and setup_commands and not self._course_setup_done.get(course_id):
            await self._run_course_setup(sbx, course_id, setup_commands)

        code_sig = hashlib.sha256(source_code.encode("utf-8")).hexdigest()[:8]
        logging.debug("Run start key=%s lang=%s code_sig=%s size=%d", key, language, code_sig, len(source_code))

        # Try fast-path first (instant for common languages)
        norm_lang = language.lower().strip()
        if norm_lang in FAST_PATH_TEMPLATES:
            logging.info("Fast-path provisioning check lang=%s key=%s", norm_lang, key)
            await self._ensure_runtime(sbx, norm_lang)
            try:
                result = await self._fast_path_execute(sbx, norm_lang, source_code, stdin)
                if result.status != "error":
                    logging.debug("Fast-path success lang=%s", norm_lang)
                    return result
                # Fast-path failed, fall through to AI
                logging.debug("Fast-path failed lang=%s, trying AI", norm_lang)
            except Exception:
                logging.debug("Fast-path exception lang=%s, trying AI", norm_lang, exc_info=True)

        # Try cached plan
        cache_key = self._plan_cache_key(course_id, language, source_code)
        cached_plan = self._plan_cache.get(cache_key)
        if cached_plan:
            logging.debug("Using cached plan cache_key=%s", cache_key)
            result = await self._apply_execution_plan(
                sbx=sbx,
                plan=cached_plan,
                source_code=source_code,
                language=language,
                lesson_id=lesson_id,
            )
            if result.status != "error":
                return result
            logging.debug("Cached plan failed, trying AI")

        # AI fallback
        result = await self._plan_and_execute_with_ai(
            sbx=sbx,
            source_code=source_code,
            language=language,
            stdin=stdin,
            user_id=user_id,
            lesson_id=lesson_id,
            cache_key=cache_key,
        )

        # Detect sandbox context restarts and reset the session to keep things healthy
        if self._is_context_restart(result):
            logging.warning("E2B context restarted during run key=%s lang=%s code_sig=%s", key, language, code_sig)
            await self._reset_session(key)
            # Return actionable message
            hint = (
                "The execution context was restarted by the sandbox (likely due to memory/time limits). "
                "Try reducing data sizes or splitting the work into smaller steps. The environment was reset; re-run if needed."
            )
            result.stderr = (result.stderr + "\n" + hint).strip() if result.stderr else hint
            result.status = result.status or "restarted"

        return result

    async def _run_code(self, sbx: Any, source_code: str, language: str) -> Any:
        """Run code in sandbox, handling different SDK versions."""
        try:
            return await sbx.run_code(code=source_code, language=language)
        except TypeError:
            # Fallback: some versions accept positional parameters
            return await sbx.run_code(source_code, language=language)

    async def _run_code_with_handling(self, sbx: Any, source_code: str, language: str) -> Any:
        try:
            return await self._run_code(sbx, source_code, language)
        except TimeoutException as exc:  # type: ignore[misc]
            msg = "Execution timed out in the sandbox. Try simplifying the workload or increasing the timeout."
            raise CodeExecutionError(msg, status_code=504, error_code="timeout") from exc
        except RateLimitException as exc:  # type: ignore[misc]
            msg = "Sandbox rate limit exceeded. Please wait before retrying your code."
            raise CodeExecutionError(msg, status_code=429, error_code="rate_limit") from exc
        except InvalidArgumentException as exc:  # type: ignore[misc]
            msg = "Invalid execution request sent to the sandbox. Check language and inputs."
            raise CodeExecutionError(msg, status_code=400, error_code="invalid_argument") from exc
        except NotEnoughSpaceException as exc:  # type: ignore[misc]
            msg = "The sandbox ran out of available space while executing the code."
            raise CodeExecutionError(msg, status_code=507, error_code="insufficient_storage") from exc
        except AuthenticationException as exc:  # type: ignore[misc]
            msg = "Sandbox authentication failed. Verify execution credentials."
            raise CodeExecutionError(msg, status_code=502, error_code="authentication") from exc
        except SandboxException as exc:  # type: ignore[misc]
            msg = "Sandbox returned an error while running the code."
            raise CodeExecutionError(msg, status_code=502, error_code="sandbox_error") from exc

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
        if sbx:
            try:
                closer = getattr(sbx, "close", None)
                if callable(closer):
                    await _maybe_await(closer())
                else:
                    acloser = getattr(sbx, "aclose", None)
                    if callable(acloser):
                        await _maybe_await(acloser())
            except Exception:
                logging.exception("Failed to close sandbox during reset key=%s", key)

    def _plan_cache_key(self, course_id: str | None, language: str, source_code: str) -> str:
        """Generate cache key for execution plans."""
        # Use first 50 chars to capture import/structure patterns
        code_prefix = source_code[:50].strip()
        code_hash = hashlib.sha256(code_prefix.encode()).hexdigest()[:16]
        return f"{course_id or '_'}:{language.lower()}:{code_hash}"

    async def _run_course_setup(self, sbx: Any, course_id: str, setup_commands: list[str]) -> None:
        """Run course setup commands once per sandbox."""
        logging.info("Running course setup course_id=%s commands=%d", course_id, len(setup_commands))
        for cmd in setup_commands:
            try:
                result = await sbx.commands.run(cmd)
                if result.exit_code != 0:
                    logging.warning("Setup command failed: %s (exit=%d)", cmd, result.exit_code)
            except Exception:
                logging.exception("Setup command exception: %s", cmd)
        self._course_setup_done[course_id] = True

    async def _ensure_runtime(self, sbx: Any, language: str) -> None:
        """Install language runtime for fast-path execution when missing."""
        installers = FAST_PATH_INSTALLERS.get(language)
        if not installers:
            return

        sentinel_path = f"{self._language_sentinel_prefix}{language}"
        try:
            await sbx.files.read(sentinel_path)
            return
        except Exception:
            logging.debug("Runtime sentinel missing for %s, proceeding with provisioning", language, exc_info=True)

        try:
            result = await sbx.commands.run(f"command -v {language}", timeout=60)
            if getattr(result, "exit_code", None) == 0:
                await sbx.files.write(sentinel_path, "present")
                return
        except Exception:
            logging.debug("Runtime presence check failed for %s", language, exc_info=True)

        logging.info("Installing runtime lang=%s commands=%s", language, installers)
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
        filepath = f"/home/user/{template['file']}"

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
        cache_key: str | None = None,
    ) -> ExecutionResult:
        sandbox_state = await self._gather_sandbox_state(sbx)
        plan = await self._ai_service.generate_execution_plan(
            language=language,
            source_code=source_code,
            stderr=None,
            stdin=stdin,
            sandbox_state=sandbox_state,
            user_id=user_id,
        )

        # Cache the plan for future use
        if cache_key:
            self._plan_cache[cache_key] = plan
            logging.debug("Cached execution plan cache_key=%s", cache_key)

        return await self._apply_execution_plan(
            sbx=sbx,
            plan=plan,
            source_code=source_code,
            language=language,
            lesson_id=lesson_id,
        )

    async def _gather_sandbox_state(self, sbx: Any) -> dict[str, Any]:
        state: dict[str, Any] = {}
        try:
            await sbx.files.read(self._apt_sentinel)
            state["apt_updated"] = True
        except Exception:
            state["apt_updated"] = False
        return state

    async def _apply_execution_plan(
        self,
        *,
        sbx: Any,
        plan: Any,
        source_code: str,
        language: str,
        lesson_id: str | None,
    ) -> ExecutionResult:
        stdout_chunks: list[str] = []
        stderr_chunks: list[str] = []

        # Materialize files requested by the plan
        if getattr(plan, "files", None):
            for file_entry in plan.files:
                try:
                    await sbx.files.write(path=file_entry.path, data=file_entry.content)
                except Exception:
                    logging.exception("Failed to write file %s", file_entry.path)
                    raise

        # Execute setup, install, and run commands sequentially
        envs = dict(getattr(plan, "environment", {}) or {})
        if getattr(plan, "actions", None):
            source_code = await self._apply_actions(
                sbx=sbx,
                actions=list(plan.actions),
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
        else:
            exec_result = await self._run_code_with_handling(sbx, source_code, language)
            sandbox_result = self._extract_result(exec_result)
            if sandbox_result.stdout:
                stdout_chunks.append(sandbox_result.stdout)
            if sandbox_result.stderr:
                stderr_chunks.append(sandbox_result.stderr)
            return sandbox_result

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

    async def _run_command_list(
        self,
        sbx: Any,
        commands: list[str],
        envs: dict[str, str],
        stdout_chunks: list[str],
        stderr_chunks: list[str],
        *,
        user: str | None = None,
    ) -> None:
        if not commands:
            return

        for command in commands:
            normalized_command = command.strip()
            if not normalized_command:
                continue
            logging.info("Sandbox command user=%s cmd=%s", user or "sandbox", normalized_command)
            try:
                result = await sbx.commands.run(
                    cmd=normalized_command,
                    envs=envs or None,
                    timeout=240,
                    request_timeout=300,
                    user=user,
                )
            except CommandExitException as exc:  # type: ignore[misc]
                stderr_chunks.append(exc.stderr)
                error_message = f"Command failed: {normalized_command}"
                raise CodeExecutionError(
                    error_message,
                    status_code=400,
                    error_code="command_failed",
                ) from exc
            except Exception as exc:  # pragma: no cover
                logging.exception("Command execution failed: %s", command)
                error_message = f"Command execution failed: {normalized_command}"
                raise CodeExecutionError(
                    error_message,
                    status_code=500,
                    error_code="command_error",
                ) from exc

            if getattr(result, "stdout", None):
                stdout_chunks.append(result.stdout)
            if getattr(result, "stderr", None):
                stderr_chunks.append(result.stderr)

            if "apt-get update" in normalized_command:
                try:
                    await sbx.files.write(self._apt_sentinel, "updated")
                except Exception:
                    logging.exception("Failed to record apt sentinel")

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
                    logging.debug("Skipping empty command action")
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
            logging.warning("Patch action missing replacement text path=%s", action.path)
            return current_source

        path = action.path
        replacement = action.replacement
        original = action.original or ""

        if path:
            try:
                existing = await sbx.files.read(path)
            except Exception:
                logging.debug("Patch target missing, creating file path=%s", path, exc_info=True)
                existing = None

            if existing and original and original in existing:
                new_content = existing.replace(original, replacement, 1)
            else:
                new_content = replacement

            try:
                await sbx.files.write(path=path, data=new_content)
                logging.info("Applied sandbox patch path=%s", path)
            except Exception:
                logging.exception("Failed to write patched file path=%s", path)
                raise
        else:
            logging.warning("Patch action missing path; skipping file write")

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
            lesson_uuid = UUID(lesson_id)
        except (ValueError, TypeError):
            logging.debug("Invalid lesson_id for patch persistence lesson_id=%s", lesson_id)
            return

        try:
            async with async_session_maker() as session:
                try:
                    lesson = await session.get(Lesson, lesson_uuid)
                    if lesson is None:
                        logging.debug("Lesson not found for patch persistence lesson_id=%s", lesson_id)
                        return

                    existing_content = lesson.content or ""
                    updated_content = self._replace_source_with_patch(existing_content, original, replacement)

                    if existing_content == updated_content:
                        if original:
                            logging.debug("Original snippet not found in lesson content lesson_id=%s", lesson_id)
                        return

                    lesson.content = updated_content
                    await session.commit()
                    logging.info("Persisted AI patch to lesson lesson_id=%s", lesson_id)
                except Exception:
                    await session.rollback()
                    raise
        except Exception:
            logging.exception("Failed to persist patch for lesson lesson_id=%s", lesson_id)
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
