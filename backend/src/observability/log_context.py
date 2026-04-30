"""Request-scoped log context shared by stdlib logging and structlog processors."""

import uuid
from contextvars import ContextVar, Token


type LogContextValue = str | int | float | bool | uuid.UUID | None


_LOG_CONTEXT: ContextVar[dict[str, LogContextValue] | None] = ContextVar("log_context", default=None)


def get_log_context() -> dict[str, LogContextValue]:
    """Return a shallow copy of the active request-scoped log context."""
    current = _LOG_CONTEXT.get()
    if current is None:
        return {}
    return dict(current)


def set_log_context(**values: LogContextValue) -> Token[dict[str, LogContextValue] | None]:
    """Replace the current request-scoped log context and return reset token."""
    context: dict[str, LogContextValue] = {key: value for key, value in values.items() if value is not None}
    return _LOG_CONTEXT.set(context)


def update_log_context(**values: LogContextValue) -> None:
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


def reset_log_context(token: Token[dict[str, LogContextValue] | None]) -> None:
    """Restore the previous request-scoped log context."""
    _LOG_CONTEXT.reset(token)
