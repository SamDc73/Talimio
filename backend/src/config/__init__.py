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

    # First try to get from defined settings fields (with validation/type conversion)
    value = getattr(settings, key.lower(), None)
    if value is not None:
        return value

    # Fallback to accessing raw environment data for any undefined variables
    # This uses the `extra="allow"` setting in Settings to capture all env vars
    value = settings.__dict__.get(key.upper(), default)
    if value is not None:
        return value

    # Final fallback
    return settings.__dict__.get(key.lower(), default)


__all__ = ["Settings", "env", "get_settings"]
