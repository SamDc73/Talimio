from uuid import UUID

from src.core.exceptions import ResourceNotFoundError


class RoadmapNotFound(ResourceNotFoundError):
    """Exception raised when a roadmap is not found."""

    def __init__(self, roadmap_id: UUID) -> None:
        super().__init__("Roadmap", str(roadmap_id))
