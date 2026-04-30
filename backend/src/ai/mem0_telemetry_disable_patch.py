"""Hard-disable mem0 telemetry (PostHog) at runtime.

Why this exists
---------------
mem0 initializes PostHog telemetry at import time via `mem0.memory.telemetry`.
Even when telemetry is "disabled", this can still create background worker
threads (and, in some cases, interfere with clean FastAPI/Uvicorn shutdown).

We want Talimio to default to **no telemetry** without requiring env vars.

Approach
--------
1) Install a no-op `posthog` module/class into `sys.modules` before mem0 is
   imported, so mem0's `from posthog import Posthog` can't start the real client.
2) After mem0 is imported, overwrite mem0's `capture_event` hooks to no-ops so
   mem0 doesn't instantiate extra telemetry helpers per call.

This is intentionally small and idempotent, mirroring the pattern used for the
LiteLLM embedder patch.
"""

import sys
import types
from collections.abc import Callable


_POSTHOG_PATCHED = False
_MEM0_HOOKS_PATCHED = False


class _NoOpPosthog:
    """Drop-in replacement for `posthog.Posthog` that never spawns workers."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.disabled = True

    def capture(self, *args: object, **kwargs: object) -> None:
        del args, kwargs

    def shutdown(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


def _install_noop_posthog_module() -> None:
    """Ensure future `import posthog` resolves to a no-op implementation."""
    existing = sys.modules.get("posthog")
    if existing is not None:
        existing.__dict__["Posthog"] = _NoOpPosthog
        return

    module = types.ModuleType("posthog")
    module.__dict__["Posthog"] = _NoOpPosthog
    sys.modules["posthog"] = module


def _noop(*_args: object, **_kwargs: object) -> None:
    return None


def apply_mem0_telemetry_disable_patch() -> None:
    """Disable mem0 telemetry by patching PostHog + mem0 capture hooks (idempotent)."""
    global _POSTHOG_PATCHED, _MEM0_HOOKS_PATCHED  # noqa: PLW0603

    if not _POSTHOG_PATCHED:
        _install_noop_posthog_module()
        _POSTHOG_PATCHED = True

    # Patch mem0 hooks when mem0 is importable (call again after importing mem0).
    if not _MEM0_HOOKS_PATCHED:
        try:
            import mem0.memory.main as mem0_main

            mem0_main.__dict__["capture_event"] = _noop
        except ImportError:
            pass

        try:
            import mem0.memory.telemetry as mem0_telemetry

            mem0_telemetry.__dict__["capture_event"] = _noop
            mem0_telemetry.__dict__["capture_client_event"] = _noop

            client = getattr(mem0_telemetry, "client_telemetry", None)
            close_client: Callable[[], object] | None = getattr(client, "close", None) if client is not None else None
            if callable(close_client):
                close_client()
        except ImportError:
            pass

        _MEM0_HOOKS_PATCHED = "mem0.memory.main" in sys.modules or "mem0.memory.telemetry" in sys.modules
