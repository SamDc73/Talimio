"""Centralized LiteLLM process configuration."""

import logging
import os
from typing import Any, cast

import litellm


_LITELLM_CONFIGURED = False


def _normalize_callbacks(raw_callbacks: Any) -> list[Any]:
    """Normalize LiteLLM callback config to a mutable list."""
    if raw_callbacks is None:
        return []
    if isinstance(raw_callbacks, list):
        return list(raw_callbacks)
    if isinstance(raw_callbacks, tuple):
        return list(raw_callbacks)
    return [raw_callbacks]


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
