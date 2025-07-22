"""Pydantic schemas for the unified courses API."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class LessonBase(BaseModel):
    """Base schema for lessons."""

    slug: str = Field(..., description="Lesson slug")
    md_source: str = Field(..., description="Lesson content in Markdown")
    html_cache: str | None = Field(None, description="Cached HTML content")


class LessonCreate(BaseModel):
    """Schema for creating a new lesson."""

    slug: str = Field(..., description="Lesson slug")
    node_meta: dict = Field(..., description="Node metadata for lesson generation")


class LessonUpdate(BaseModel):
    """Schema for updating a lesson."""

    slug: str | None = Field(None, description="Lesson slug")
    md_source: str | None = Field(None, description="Lesson content in Markdown")
    html_cache: str | None = Field(None, description="Cached HTML content")


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
    citations: list[LessonCitation] = Field(default_factory=list, description="Lesson citations")
    created_at: datetime = Field(..., description="Lesson creation timestamp")
    updated_at: datetime = Field(..., description="Lesson last update timestamp")

    # Additional fields for web app compatibility
    title: str | None = Field(None, description="Lesson title extracted from content")
    description: str | None = Field(None, description="Lesson description")
    content: str | None = Field(None, description="Lesson content as HTML")

    model_config = ConfigDict(from_attributes=True)


class CourseBase(BaseModel):
    """Base schema for courses (formerly roadmaps)."""

    title: str = Field(..., description="Course title")
    description: str = Field("", description="Course description")
    skill_level: str = Field("beginner", description="Course skill level")
    tags_json: str = Field("[]", description="Course tags as JSON string")
    archived: bool = Field(default=False, description="Whether the course is archived")
    rag_enabled: bool = Field(default=False, description="Whether RAG is enabled for this course")


class CourseCreate(BaseModel):
    """Schema for creating a new course."""

    prompt: str = Field(..., description="AI prompt for course generation")


class CourseUpdate(BaseModel):
    """Schema for updating a course."""

    title: str | None = Field(None, description="Course title")
    description: str | None = Field(None, description="Course description")
    skill_level: str | None = Field(None, description="Course skill level")
    tags_json: str | None = Field(None, description="Course tags as JSON string")
    archived: bool | None = Field(None, description="Whether the course is archived")
    rag_enabled: bool | None = Field(None, description="Whether RAG is enabled for this course")


class CourseResponse(CourseBase):
    """Schema for course responses."""

    id: UUID = Field(..., description="Course ID")
    archived_at: datetime | None = Field(None, description="Course archive timestamp")
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


class CourseProgressResponse(BaseModel):
    """Schema for course progress responses."""

    course_id: UUID = Field(..., description="Course ID")
    total_modules: int = Field(..., description="Total number of modules")
    completed_modules: int = Field(..., description="Number of completed modules")
    in_progress_modules: int = Field(..., description="Number of modules in progress")
    completion_percentage: float = Field(..., description="Overall course completion percentage")
    total_lessons: int = Field(..., description="Total number of lessons")
    completed_lessons: int = Field(..., description="Number of completed lessons")


class LessonStatusUpdate(BaseModel):
    """Schema for updating lesson status."""

    status: str = Field(..., description="Lesson status: not_started, in_progress, completed")


class LessonStatusResponse(BaseModel):
    """Schema for lesson status responses."""

    lesson_id: UUID = Field(..., description="Lesson ID")
    module_id: UUID = Field(..., description="Module ID")
    course_id: UUID = Field(..., description="Course ID")
    status: str = Field(..., description="Lesson status")
    created_at: datetime = Field(..., description="Status creation timestamp")
    updated_at: datetime = Field(..., description="Status last update timestamp")

    model_config = ConfigDict(from_attributes=True)


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
