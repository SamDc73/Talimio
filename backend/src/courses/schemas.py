"""Pydantic schemas for the unified courses API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LessonBase(BaseModel):
    """Base schema for lessons."""

    html_cache: str | None = Field(None, description="Cached HTML content")

    # Additional fields for web app compatibility
    title: str | None = Field(None, description="Lesson title extracted from content")
    description: str | None = Field(None, description="Lesson description")
    model_config = ConfigDict(from_attributes=True)


class LessonCitation(BaseModel):
    """Schema for lesson citations."""

    document_id: int = Field(..., description="Document ID")
    document_title: str = Field(..., description="Document title")
    similarity_score: float = Field(..., description="Similarity score")


class LessonResponse(LessonBase):
    """Schema for lesson responses."""

    id: UUID = Field(..., description="Lesson ID")
    course_id: UUID = Field(..., description="Course ID")
    module_id: UUID = Field(..., description="Module ID")
    content: str | None = Field(None, description="Lesson content (MDX format)")
    citations: list[LessonCitation] = Field(default_factory=list, description="Lesson citations")
    created_at: datetime = Field(..., description="Lesson creation timestamp")
    updated_at: datetime = Field(..., description="Lesson last update timestamp")


class CourseBase(BaseModel):
    """Base schema for courses (formerly roadmaps)."""

    title: str = Field(..., description="Course title")
    description: str = Field("", description="Course description")
    tags: str = Field("[]", description="Course tags as JSON string")
    archived: bool = Field(default=False, description="Whether the course is archived")


class CourseCreate(BaseModel):
    """Schema for creating a new course."""

    prompt: str = Field(..., min_length=1, description="AI prompt for course generation")


class CourseUpdate(BaseModel):
    """Schema for updating a course."""

    title: str | None = Field(None, description="Course title")
    description: str | None = Field(None, description="Course description")
    tags: str | None = Field(None, description="Course tags as JSON string")
    archived: bool | None = Field(None, description="Whether the course is archived")


class CourseResponse(CourseBase):
    """Schema for course responses."""

    id: UUID = Field(..., description="Course ID")
    created_at: datetime = Field(..., description="Course creation timestamp")
    updated_at: datetime = Field(..., description="Course last update timestamp")
    modules: list["ModuleResponse"] = Field(default_factory=list, description="Course modules")

    model_config = ConfigDict(from_attributes=True)


class CourseListResponse(BaseModel):
    """Schema for course list responses with pagination."""

    courses: list[CourseResponse] = Field(..., description="List of courses")
    total: int = Field(..., description="Total number of courses")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of courses per page")


class ModuleResponse(BaseModel):
    """Schema for module responses."""

    id: UUID = Field(..., description="Module ID")
    course_id: UUID = Field(..., description="Course ID")
    title: str = Field(..., description="Module title")
    description: str | None = Field(None, description="Module description")
    content: str | None = Field(None, description="Module content")
    order: int = Field(..., description="Module order")
    status: str = Field(..., description="Module status")
    completion_percentage: float = Field(..., description="Module completion percentage")
    parent_id: UUID | None = Field(None, description="Parent module ID")
    created_at: datetime = Field(..., description="Module creation timestamp")
    updated_at: datetime = Field(..., description="Module last update timestamp")
    lessons: list["LessonResponse"] = Field(default_factory=list, description="Module lessons")

    model_config = ConfigDict(from_attributes=True)


class MDXValidateRequest(BaseModel):
    """Request schema for MDX validation."""

    content: str = Field(..., description="MDX content to validate")


class MDXValidateResponse(BaseModel):
    """Response schema for MDX validation."""

    valid: bool = Field(..., description="Whether the MDX content is valid")
    error: str | None = Field(None, description="Error message if validation failed")
    metadata: dict | None = Field(None, description="Additional metadata from validation")


# NOTE: Quiz schemas removed - quizzes are embedded in lesson content (MDX)
# Quiz results are handled through lesson progress updates, not separate submissions
