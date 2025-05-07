"""Schemas for progress API."""

from datetime import datetime

from pydantic import BaseModel, Field, validator


class StatusUpdate(BaseModel):
    """Schema for updating lesson status."""

    status: str = Field(
        ...,
        description="Lesson status",
        pattern="^(not_started|in_progress|done)$",
    )

    @validator("status")
    def validate_status(self, v: str) -> str:
        """Validate status value."""
        allowed_values = ["not_started", "in_progress", "done"]
        if v not in allowed_values:
            msg = f"Status must be one of: {', '.join(allowed_values)}"
            raise ValueError(msg)
        return v


class LessonStatusResponse(BaseModel):
    """Schema for lesson status response."""

    lesson_id: str
    status: str
    updated_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class CourseProgressResponse(BaseModel):
    """Schema for course progress response."""

    course_id: str
    total_lessons: int
    completed_lessons: int
    progress_percentage: int


class LessonStatus(BaseModel):
    """Schema for individual lesson status."""

    id: str
    status: str


class LessonStatusesResponse(BaseModel):
    """Schema for list of lesson statuses."""

    lessons: list[LessonStatus]


class ErrorResponse(BaseModel):
    """Schema for error response."""

    error: str
