"""Environment access helper backed by pydantic settings."""

from typing import Any

from .settings import get_settings


def env(key: str, default: Any = None) -> Any:
    """Access any environment variable through settings."""
    settings = get_settings()
    normalized_upper = key.upper()
    normalized_lower = key.lower()

    # First try to get from defined settings fields (with validation/type conversion).
    for field_name in (normalized_upper, normalized_lower, key):
        if field_name in type(settings).model_fields:
            value = getattr(settings, field_name)
            if value is not None:
                return value

    # Fallback to raw environment extras captured by Settings(extra="allow").
    extra = settings.model_extra or {}
    for extra_key in (key, normalized_upper, normalized_lower):
        if extra_key in extra:
            value = extra.get(extra_key)
            if value is not None:
                return value

    return default


__all__ = ["env"]
