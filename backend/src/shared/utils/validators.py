import uuid


def validate_uuid(value: str | int | uuid.UUID) -> bool:
    """Validate if a string is a valid UUID."""
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    else:
        return True
