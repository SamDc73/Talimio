"""Centralized structlog + stdlib logging configuration for local and cloud environments."""

import json
import logging
import logging.config
import re
from collections.abc import MutableMapping
from typing import Any, cast

import structlog
from opentelemetry import trace

from src.config.settings import Settings, get_settings
from src.observability.event_fields import get_feature_area
from src.observability.log_context import get_log_context
from src.observability.resources import resolve_release_version


SERVICE_NAME = "api"
_UVICORN_ACCESS_LOGGER_NAME = "uvicorn.access"
_CONTEXT_EVENT_FIELDS: tuple[str, ...] = (
    "route",
    "feature_area",
    "user_id",
    "session_id",
    "course_id",
    "content_type",
    "model_name",
    "status_code",
    "error_code",
)
_PROCESSOR_INTERNAL_FIELDS = {
    "_record",
    "_from_structlog",
    "exc_info",
    "stack_info",
}
_JSON_RENDERER = structlog.processors.JSONRenderer(serializer=json.dumps, default=str, ensure_ascii=True)
_LOGFMT_RENDERER = structlog.processors.LogfmtRenderer(
    key_order=[
        "level",
        "message",
        "event",
        "logger",
        "timestamp",
        "service",
        "env",
        "release",
        "route",
        "feature_area",
        "status_code",
        "error_code",
        "trace_id",
        "span_id",
        "user_id",
        "session_id",
        "course_id",
        "content_type",
        "model_name",
    ],
    drop_missing=True,
)
_RUNTIME_METADATA: dict[str, str] = {
    "service": SERVICE_NAME,
    "env": "development",
    "release": "",
}


def _normalize_event_name(raw_value: Any, fallback: str) -> str:
    text_value = str(raw_value).strip() if raw_value is not None else ""
    if not text_value:
        text_value = fallback
    normalized = re.sub(r"[^a-z0-9.]+", "_", text_value.lower()).strip("._")
    return normalized or fallback


def _is_message_event_name(message: str) -> bool:
    if " " in message:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._-]+", message))


def _resolve_logging_mode(environment: str, revision: str) -> str:
    return "json" if environment == "production" or revision else "pretty"


def _set_runtime_metadata(*, env: str, release: str) -> None:
    _RUNTIME_METADATA["env"] = env
    _RUNTIME_METADATA["release"] = release


def _attach_request_context(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    context = get_log_context()
    for field_name in _CONTEXT_EVENT_FIELDS:
        current_value = event_dict.get(field_name)
        if current_value in {None, ""}:
            context_value = context.get(field_name)
            if context_value not in {None, ""}:
                event_dict[field_name] = context_value
    return event_dict


def _attach_access_log_context(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    record = event_dict.get("_record")
    if not isinstance(record, logging.LogRecord) or record.name != _UVICORN_ACCESS_LOGGER_NAME:
        return event_dict

    raw_args = getattr(record, "args", ())
    if not isinstance(raw_args, tuple) or len(raw_args) < 5:
        return event_dict

    args = cast("tuple[Any, ...]", raw_args)
    route = event_dict.get("route") or str(args[2])
    if event_dict.get("route") in {None, ""}:
        event_dict["route"] = route
    if event_dict.get("status_code") in {None, ""}:
        event_dict["status_code"] = args[4]
    if event_dict.get("feature_area") in {None, ""}:
        event_dict["feature_area"] = get_feature_area(str(route))
    return event_dict


def _attach_trace_context(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    if event_dict.get("trace_id") not in {None, ""} and event_dict.get("span_id") not in {None, ""}:
        return event_dict

    current_span = trace.get_current_span()
    get_span_context = getattr(current_span, "get_span_context", None)
    if not callable(get_span_context):
        return event_dict

    span_context = get_span_context()
    if not span_context.is_valid:
        return event_dict

    event_dict.setdefault("trace_id", f"{span_context.trace_id:032x}")
    event_dict.setdefault("span_id", f"{span_context.span_id:016x}")
    return event_dict


def _normalize_event_contract(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> MutableMapping[str, Any]:
    record = event_dict.get("_record")
    logger_name = event_dict.get("logger")

    raw_message = event_dict.get("event", "")
    message = "" if raw_message is None else str(raw_message)

    explicit_event_name = event_dict.pop("event_name", None)
    if explicit_event_name in {None, ""} and isinstance(record, logging.LogRecord):
        explicit_event_name = getattr(record, "event", None)
    if explicit_event_name in {None, ""} and message and _is_message_event_name(message):
        explicit_event_name = message

    fallback_event_name = "http_access" if logger_name == _UVICORN_ACCESS_LOGGER_NAME else str(logger_name or "app")
    normalized_event = _normalize_event_name(
        explicit_event_name if explicit_event_name not in {None, ""} else fallback_event_name,
        fallback=fallback_event_name,
    )

    event_dict["event"] = normalized_event
    event_dict["message"] = message
    event_dict.setdefault("service", _RUNTIME_METADATA["service"])
    event_dict.setdefault("env", _RUNTIME_METADATA["env"])
    event_dict.setdefault("release", _RUNTIME_METADATA["release"])

    level = event_dict.get("level")
    if isinstance(level, str):
        event_dict["level"] = level.upper()

    route = event_dict.get("route")
    if route not in {None, ""} and event_dict.get("feature_area") in {None, ""}:
        event_dict["feature_area"] = get_feature_area(str(route))

    return event_dict


def _render_json(
    _logger: Any,
    _method_name: str,
    event_dict: MutableMapping[str, Any],
) -> str:
    payload = {
        key: value
        for key, value in event_dict.items()
        if key not in _PROCESSOR_INTERNAL_FIELDS and (key == "route" or value not in {None, ""})
    }
    rendered = _JSON_RENDERER(_logger, _method_name, payload)
    if isinstance(rendered, bytes):
        return rendered.decode("utf-8", errors="replace")
    return rendered


def _build_shared_processors() -> list[Any]:
    return [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _attach_request_context,
        _attach_access_log_context,
        _attach_trace_context,
        _normalize_event_contract,
    ]


def setup_logging(settings: Settings | None = None) -> None:
    """Configure structlog processors and stdlib handlers for app and third-party logs."""
    resolved_settings = settings or get_settings()
    release = resolve_release_version(resolved_settings)
    formatter_name = _resolve_logging_mode(resolved_settings.ENVIRONMENT, resolved_settings.K_REVISION.strip())
    level = "DEBUG" if resolved_settings.DEBUG else "INFO"

    _set_runtime_metadata(env=resolved_settings.ENVIRONMENT, release=release)
    shared_processors = _build_shared_processors()

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "pretty": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": shared_processors,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.format_exc_info,
                    _LOGFMT_RENDERER,
                ],
            },
            "json": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": shared_processors,
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    structlog.processors.format_exc_info,
                    _render_json,
                ],
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": formatter_name,
                "level": level,
            }
        },
        "root": {"level": level, "handlers": ["console"]},
        "loggers": {
            "uvicorn": {"level": level, "handlers": ["console"], "propagate": False},
            "uvicorn.error": {"level": level, "handlers": ["console"], "propagate": False},
            _UVICORN_ACCESS_LOGGER_NAME: {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "python_multipart": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "python_multipart.multipart": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "httpcore": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "httpx": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "LiteLLM": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "litellm": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "mem0": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "charset_normalizer": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "unstructured": {"level": "WARNING", "handlers": ["console"], "propagate": False},
            "unstructured.trace": {"level": "WARNING", "handlers": ["console"], "propagate": False},
        },
    }

    logging.config.dictConfig(config)
