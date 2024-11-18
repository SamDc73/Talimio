from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field
from src.domain.exceptions.base import DomainException


class RoadmapBase(BaseModel):
    """Base schema for roadmap data."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    skill_level: str = Field(..., pattern="^(beginner|intermediate|advanced)$")


class RoadmapCreate(RoadmapBase):
    """Schema for creating a roadmap."""

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Machine Learning Engineer Roadmap",
                "description": "Complete roadmap to become an ML engineer",
                "skill_level": "beginner",
            },
        }



class RoadmapUpdate(BaseModel):
    """Schema for updating a roadmap.

    Note: We don't inherit from RoadmapBase to allow optional fields.
    """

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, min_length=1)
    skill_level: str | None = Field(None, pattern="^(beginner|intermediate|advanced)$")


class RoadmapResponse(RoadmapBase):
    """Schema for roadmap response."""

    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "title": "Machine Learning Engineer Roadmap",
                "description": "Complete roadmap to become an ML engineer",
                "skill_level": "beginner",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z",
            },
        }


class RoadmapsListResponse(BaseModel):
    """Schema for paginated roadmaps list."""

    items: list[RoadmapResponse]
    total: int
    page: int
    pages: int




class RoadmapNotFound(DomainException):
    """Raised when roadmap is not found."""

    def __init__(self, roadmap_id: UUID) -> None:
        super().__init__(f"Roadmap with ID {roadmap_id} not found")
