"""Pydantic models for AI-related data structures."""

from pydantic import BaseModel, ConfigDict, Field


class Lesson(BaseModel):
    """Model for a lesson in the course structure."""

    title: str = Field(description="Title of the lesson")
    description: str = Field(description="Brief description of what the lesson covers")
    module: str | None = Field(
        default=None, description="Optional module/section name for grouping"
    )

    model_config = ConfigDict(extra="forbid")


class CourseStructure(BaseModel):
    """Model for the course/roadmap structure returned by AI."""

    title: str
    description: str
    # Required list to satisfy strict schema requirement (no default)
    lessons: list[Lesson]

    model_config = ConfigDict(extra="forbid")


class LessonContent(BaseModel):
    """Model for lesson content returned by AI."""

    body: str = Field(description="The full lesson content in Markdown format")

    model_config = ConfigDict(extra="forbid")
