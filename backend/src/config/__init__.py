from typing import Any

from .settings import Settings, get_settings


def env(key: str, default: Any = None) -> Any:
    """Access any environment variable through settings.

    This provides a unified way to access environment variables while leveraging
    Pydantic's BaseSettings for validation and type conversion where needed.

    Args:
        key: Environment variable key (case insensitive)
        default: Default value if not found

    Returns
    -------
        The environment variable value or default
    """
    settings = get_settings()
    normalized_upper = key.upper()
    normalized_lower = key.lower()

    # First try to get from defined settings fields (with validation/type conversion)
    for field_name in (normalized_upper, normalized_lower, key):
        if field_name in settings.model_fields:
            value = getattr(settings, field_name)
            if value is not None:
                return value

    # Fallback to accessing raw environment data for any undefined variables
    # This uses the `extra="allow"` setting in Settings to capture all env vars
    extra = settings.model_extra or {}
    for extra_key in (key, normalized_upper, normalized_lower):
        if extra_key in extra:
            value = extra.get(extra_key)
            if value is not None:
                return value

    # Final fallback
    return default


__all__ = ["Settings", "env", "get_settings"]
