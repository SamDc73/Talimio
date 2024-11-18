class DomainException(Exception):
    """Base exception class for all domain-specific exceptions."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(self.message)


class RoadmapException(DomainException):
    """Base exception class for roadmap-related exceptions."""



class ResourceNotFoundException(DomainException):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type} with ID {resource_id} not found"
        super().__init__(message)
