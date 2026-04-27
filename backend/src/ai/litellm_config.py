"""Centralized LiteLLM process configuration."""

import logging
import os
from datetime import datetime
from typing import Any, cast

import litellm
import structlog
from litellm.integrations.custom_logger import CustomLogger


_LITELLM_CONFIGURED = False
_LLM_COMPLETION_CALL_TYPES = {
    "completion",
    "acompletion",
    "responses",
    "aresponses",
    "text_completion",
    "atext_completion",
    "generate_content",
    "agenerate_content",
    "generate_content_stream",
    "agenerate_content_stream",
}
logger = structlog.get_logger(__name__)


class _LLMCompletionLogger(CustomLogger):
    def log_success_event(self, kwargs: dict[str, Any], response_obj: Any, start_time: Any, end_time: Any) -> None:
        call_type = _get_call_type(kwargs)
        if call_type is not None and call_type not in _LLM_COMPLETION_CALL_TYPES:
            return

        duration_ms = _calculate_duration_ms(start_time, end_time)
        logger.info(
            "ai.llm.completed",
            event_name="ai.llm.completed",
            model=_get_model_name(kwargs, response_obj),
            duration_ms=duration_ms,
        )

    async def async_log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: Any,
        end_time: Any,
    ) -> None:
        self.log_success_event(kwargs, response_obj, start_time, end_time)


_LLM_COMPLETION_LOGGER = _LLMCompletionLogger()


def _normalize_callbacks(raw_callbacks: Any) -> list[Any]:
    """Normalize LiteLLM callback config to a mutable list."""
    if raw_callbacks is None:
        return []
    if isinstance(raw_callbacks, list):
        return list(raw_callbacks)
    if isinstance(raw_callbacks, tuple):
        return list(raw_callbacks)
    return [raw_callbacks]


def _calculate_duration_ms(start_time: Any, end_time: Any) -> float | None:
    if isinstance(start_time, datetime) and isinstance(end_time, datetime):
        return round((end_time - start_time).total_seconds() * 1000, 2)
    if isinstance(start_time, (int, float)) and isinstance(end_time, (int, float)):
        return round((end_time - start_time) * 1000, 2)
    return None


def _get_model_name(kwargs: dict[str, Any], response_obj: Any) -> str | None:
    model = kwargs.get("model")
    if isinstance(model, str) and model.strip():
        return model

    response_model = getattr(response_obj, "model", None)
    if isinstance(response_model, str) and response_model.strip():
        return response_model

    return None


def _get_call_type(kwargs: dict[str, Any]) -> str | None:
    call_type = kwargs.get("call_type")
    if isinstance(call_type, str) and call_type.strip():
        return call_type

    litellm_params = kwargs.get("litellm_params")
    if isinstance(litellm_params, dict):
        params_call_type = litellm_params.get("call_type")
        if isinstance(params_call_type, str) and params_call_type.strip():
            return params_call_type

    return None


def _configure_llm_completion_logger_callback() -> None:
    callbacks = _normalize_callbacks(getattr(litellm, "callbacks", []))
    if not any(isinstance(callback, _LLMCompletionLogger) for callback in callbacks):
        callbacks.append(_LLM_COMPLETION_LOGGER)
    litellm.callbacks = callbacks


def _configure_langfuse_otel_callback() -> None:
    """Enable Langfuse OTEL callback only for cloud mode with credentials."""
    callbacks = _normalize_callbacks(getattr(litellm, "callbacks", []))
    callbacks_without_langfuse = [callback for callback in callbacks if callback != "langfuse_otel"]

    platform_mode = os.getenv("PLATFORM_MODE", "cloud").strip().lower()
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    configured_host = os.getenv("LANGFUSE_OTEL_HOST", "").strip()
    base_url = os.getenv("LANGFUSE_BASE_URL", "").strip()

    is_cloud = platform_mode == "cloud"
    has_credentials = bool(public_key) and bool(secret_key)
    resolved_host = configured_host or base_url

    if not is_cloud or not has_credentials or not resolved_host:
        litellm.callbacks = callbacks_without_langfuse
        return

    if not configured_host and base_url:
        os.environ["LANGFUSE_OTEL_HOST"] = base_url

    if "langfuse_otel" not in callbacks_without_langfuse:
        callbacks_without_langfuse.append("langfuse_otel")
    litellm.callbacks = callbacks_without_langfuse


def configure_litellm() -> None:
    """Apply process-wide LiteLLM settings exactly once."""
    global _LITELLM_CONFIGURED  # noqa: PLW0603
    if _LITELLM_CONFIGURED:
        return

    # LiteLLM lazily registers an atexit cleanup hook that spins up a fresh event
    # loop during process teardown. In tests, that happens after pytest closes its
    # capture streams and produces noisy closed-file logging. We manage cleanup
    # ourselves, so keep LiteLLM from registering the extra atexit hook.
    cast("Any", litellm)._async_client_cleanup_registered = True  # noqa: SLF001
    litellm.enable_json_schema_validation = True
    litellm.drop_params = True
    # LiteLLM exposes suppress_debug_info as Literal[False]; cast avoids false-positive type errors.
    cast("Any", litellm).suppress_debug_info = True
    asyncio_logger = logging.getLogger("asyncio")
    if asyncio_logger.isEnabledFor(logging.DEBUG):
        asyncio_logger.setLevel(logging.INFO)
    _configure_langfuse_otel_callback()
    _configure_llm_completion_logger_callback()

    _LITELLM_CONFIGURED = True


async def cleanup_litellm_async_clients() -> None:
    """Close cached LiteLLM async HTTP clients used across requests."""
    close_async_clients = getattr(litellm, "close_litellm_async_clients", None)
    if callable(close_async_clients):
        await close_async_clients()

    async_client = getattr(litellm, "aclient_session", None)
    close_async_client = getattr(async_client, "aclose", None) if async_client is not None else None
    if callable(close_async_client):
        await close_async_client()
    litellm.aclient_session = None

    client = getattr(litellm, "client_session", None)
    close_client = getattr(client, "close", None) if client is not None else None
    if callable(close_client):
        close_client()
    litellm.client_session = None


__all__ = ["cleanup_litellm_async_clients", "configure_litellm"]
