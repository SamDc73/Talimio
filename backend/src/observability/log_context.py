"""Request-scoped log context shared by stdlib logging and structlog processors."""

from contextvars import ContextVar, Token
from typing import Any


_LOG_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, Any]:
    """Return a shallow copy of the active request-scoped log context."""
    current = _LOG_CONTEXT.get()
    if current is None:
        return {}
    return dict(current)


def set_log_context(**values: Any) -> Token[dict[str, Any] | None]:
    """Replace the current request-scoped log context and return reset token."""
    context = {key: value for key, value in values.items() if value is not None}
    return _LOG_CONTEXT.set(context)


def update_log_context(**values: Any) -> None:
    """Merge non-null values into the current request-scoped log context."""
    current = _LOG_CONTEXT.get()
    if current is None:
        current = {}

    for key, value in values.items():
        if value is None:
            continue
        current[key] = value

    _LOG_CONTEXT.set(current)


def clear_log_context() -> None:
    """Clear the active request-scoped log context."""
    _LOG_CONTEXT.set(None)


def reset_log_context(token: Token[dict[str, Any] | None]) -> None:
    """Restore the previous request-scoped log context."""
    _LOG_CONTEXT.reset(token)
