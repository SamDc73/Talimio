"""Domain exceptions for the learning capabilities module."""

from src.exceptions import (
    BadRequestError,
    NotFoundError,
    ValidationError,
)


FEATURE_AREA = "learning_capabilities"


class LearningCapabilitiesValidationError(ValidationError):
    """Raised when capability payload validation fails."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class LearningCapabilitiesBadRequestError(BadRequestError):
    """Raised when a capability request is invalid for current domain state."""

    def __init__(self, detail: str) -> None:
        super().__init__(detail, feature_area=FEATURE_AREA)


class LearningCapabilitiesNotFoundError(NotFoundError):
    """Raised when a capability target resource is missing or not owned."""

    def __init__(self, detail: str) -> None:
        super().__init__(message=detail, feature_area=FEATURE_AREA)
