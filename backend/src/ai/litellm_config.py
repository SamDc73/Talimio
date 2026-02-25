"""Centralized LiteLLM process configuration."""

from typing import Any, cast

import litellm


_LITELLM_CONFIGURED = False


def configure_litellm() -> None:
    """Apply process-wide LiteLLM settings exactly once."""
    global _LITELLM_CONFIGURED  # noqa: PLW0603
    if _LITELLM_CONFIGURED:
        return

    litellm.enable_json_schema_validation = True
    litellm.drop_params = True
    # LiteLLM exposes suppress_debug_info as Literal[False]; cast avoids false-positive type errors.
    cast("Any", litellm).suppress_debug_info = True

    _LITELLM_CONFIGURED = True


__all__ = ["configure_litellm"]
