import uuid
from typing import Any


def validate_uuid(value: Any) -> bool:
    """Validate if a string is a valid UUID."""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError, TypeError):
        return False
