from uuid import UUID

from src.domain.exceptions.base import ResourceNotFoundException


class RoadmapNotFound(ResourceNotFoundException):
    """Exception raised when a roadmap is not found."""

    def __init__(self, roadmap_id: UUID) -> None:
        super().__init__("Roadmap", str(roadmap_id))
