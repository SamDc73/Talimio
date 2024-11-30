class DomainError(Exception):
    """Base exception class for all domain-specific exceptions."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class ResourceNotFoundError(DomainError):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type} with ID {resource_id} not found"
        super().__init__(message)


class ValidationError(DomainError):
    """Exception raised when validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
