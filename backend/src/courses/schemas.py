"""Pydantic schemas for the unified courses API."""

from datetime import datetime
from typing import Any, Literal
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
    module_name: str | None = Field(None, description="Module grouping name")
    module_order: int | None = Field(None, description="Module ordering value")
    order: int = Field(..., description="Lesson order within module")
    content: str | None = Field(None, description="Lesson content (MDX format)")
    citations: list[LessonCitation] = Field(default_factory=list, description="Lesson citations")
    created_at: datetime = Field(..., description="Lesson creation timestamp")
    updated_at: datetime = Field(..., description="Lesson last update timestamp")


class CourseBase(BaseModel):
    """Base schema for courses."""

    title: str = Field(..., description="Course title")
    description: str = Field("", description="Course description")
    tags: str = Field("[]", description="Course tags as JSON string")
    archived: bool = Field(default=False, description="Whether the course is archived")
    setup_commands: list[str] = Field(default_factory=list, description="Commands to run once per course sandbox")


class CourseCreate(BaseModel):
    """Schema for creating a new course."""

    prompt: str = Field(..., min_length=1, description="AI prompt for course generation")


class SelfAssessmentRequest(BaseModel):
    """Request payload for generating self-assessment questions."""

    topic: str = Field(..., min_length=1, description="Course topic for personalization")
    level: str | None = Field(None, description="Optional learner experience level or confidence band")

    model_config = ConfigDict(extra="forbid")


class SelfAssessmentQuestionPayload(BaseModel):
    """Single-select question suitable for MultipleChoice component."""

    type: Literal["single_select"] = Field(..., description="Question presentation type")
    question: str = Field(..., min_length=1, description="Learner-facing question text")
    options: list[str] = Field(..., min_length=3, max_length=5, description="Candidate answers")

    model_config = ConfigDict(extra="forbid")


class SelfAssessmentResponse(BaseModel):
    """Response containing generated self-assessment questions."""

    questions: list[SelfAssessmentQuestionPayload] = Field(default_factory=list, description="Generated self-assessment questions")

    model_config = ConfigDict(extra="forbid")


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
    """Schema for synthesized module responses."""

    id: UUID = Field(..., description="Module ID")
    course_id: UUID = Field(..., description="Course ID")
    title: str = Field(..., description="Module title")
    module_name: str | None = Field(None, description="Raw module name from lessons")
    order: int = Field(..., description="Module order")
    lessons: list["LessonResponse"] = Field(default_factory=list, description="Module lessons")

    model_config = ConfigDict(from_attributes=True)


class MDXValidateRequest(BaseModel):
    """Request schema for MDX validation."""

    content: str = Field(..., description="MDX content to validate")


class MDXValidateResponse(BaseModel):
    """Response schema for MDX validation."""

    valid: bool = Field(..., description="Whether the MDX content is valid")
    error: str | None = Field(None, description="Error message if validation failed")
    metadata: dict[str, Any] | None = Field(None, description="Extracted metadata from MDX content")

# NOTE: Quiz schemas removed - quizzes are embedded in lesson content (MDX)
# Quiz results are handled through lesson progress updates, not separate submissions


class CodeExecuteRequest(BaseModel):
    """Request to execute a code snippet via E2B."""

    code: str = Field(..., min_length=1, description="Source code to execute")
    language: str = Field(..., min_length=1, description="Language name/alias, e.g., python, js, cpp")
    stdin: str | None = Field(None, description="Optional stdin input")
    lesson_id: UUID | None = Field(None, description="Optional lesson id for analytics/logging")
    course_id: UUID | None = Field(None, description="Course id for sandbox scoping and setup commands")


class CodeExecuteResponse(BaseModel):
    """Normalized execution response payload."""

    stdout: str | None = None
    stderr: str | None = None
    status: str | None = None
    time: float | None = None
    memory: float | None = None
