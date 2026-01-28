"""Pydantic schemas for the unified courses API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(string: str) -> str:
    parts = string.split("_")
    if len(parts) == 1:
        return string
    head, *tail = parts
    return head + "".join(word.capitalize() for word in tail)


_CAMEL_CONFIG = {"alias_generator": _to_camel, "populate_by_name": True}


class LessonSummary(BaseModel):
    """Lightweight lesson representation for course outlines."""

    id: UUID = Field(..., description="Lesson ID")
    title: str = Field(..., description="Lesson title")
    description: str | None = Field(None, description="Lesson description")
    order: int = Field(..., description="Lesson order within its module")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class LessonDetailResponse(BaseModel):
    """Schema for detailed lesson responses (content endpoint)."""

    id: UUID = Field(..., description="Lesson ID")
    course_id: UUID = Field(..., description="Course ID")
    title: str = Field(..., description="Lesson title")
    description: str | None = Field(None, description="Lesson description")
    content: str | None = Field(None, description="Lesson content (MDX format)")
    concept_id: UUID | None = Field(None, description="Mapped concept ID for adaptive lessons")
    adaptive_enabled: bool | None = Field(None, description="Whether the parent course is adaptive")
    created_at: datetime = Field(..., description="Lesson creation timestamp")
    updated_at: datetime = Field(..., description="Lesson last update timestamp")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class CourseBase(BaseModel):
    """Base schema for courses."""

    title: str = Field(..., description="Course title")
    description: str = Field("", description="Course description")
    tags: str = Field("[]", description="Course tags as JSON string")
    archived: bool = Field(default=False, description="Whether the course is archived")
    setup_commands: list[str] = Field(default_factory=list, description="Commands to run once per course sandbox")
    adaptive_enabled: bool = Field(default=False, description="Whether adaptive concept scheduling is enabled")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CourseCreate(BaseModel):
    """Schema for creating a new course."""

    prompt: str = Field(..., min_length=1, description="AI prompt for course generation")
    adaptive_enabled: bool = Field(default=False, description="Enable adaptive concept scheduling")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class SelfAssessmentRequest(BaseModel):
    """Request payload for generating self-assessment questions."""

    topic: str = Field(..., min_length=1, description="Course topic for personalization")
    level: str | None = Field(None, description="Optional learner experience level or confidence band")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class SelfAssessmentQuestionPayload(BaseModel):
    """Single-select question suitable for MultipleChoice component."""

    type: Literal["single_select"] = Field(..., description="Question presentation type")
    question: str = Field(..., min_length=1, description="Learner-facing question text")
    options: list[str] = Field(..., min_length=3, max_length=5, description="Candidate answers")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class SelfAssessmentResponse(BaseModel):
    """Response containing generated self-assessment questions."""

    questions: list[SelfAssessmentQuestionPayload] = Field(
        default_factory=list, description="Generated self-assessment questions"
    )

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class CourseUpdate(BaseModel):
    """Schema for updating a course."""

    title: str | None = Field(None, description="Course title")
    description: str | None = Field(None, description="Course description")
    tags: str | None = Field(None, description="Course tags as JSON string")
    archived: bool | None = Field(None, description="Whether the course is archived")
    adaptive_enabled: bool | None = Field(None, description="Enable or disable adaptive scheduling")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ModuleResponse(BaseModel):
    """Schema for synthesized module responses."""

    id: UUID = Field(..., description="Module ID")
    title: str = Field(..., description="Module title")
    description: str | None = Field(None, description="Module description")
    lessons: list[LessonSummary] = Field(default_factory=list, description="Module lessons")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class CourseResponse(CourseBase):
    """Schema for course responses."""

    id: UUID = Field(..., description="Course ID")
    user_id: UUID | None = Field(None, description="Owner user ID")
    created_at: datetime = Field(..., description="Course creation timestamp")
    updated_at: datetime = Field(..., description="Course last update timestamp")
    modules: list[ModuleResponse] = Field(default_factory=list, description="Course modules")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class CourseListResponse(BaseModel):
    """Schema for course list responses with pagination."""

    courses: list[CourseResponse] = Field(..., description="List of courses")
    total: int = Field(..., description="Total number of courses")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Number of courses per page")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ConceptSummary(BaseModel):
    """Summary of a concept for adaptive frontier responses."""

    id: UUID = Field(..., description="Concept ID")
    name: str = Field(..., description="Concept display name")
    description: str = Field(..., description="Concept description")
    difficulty: int | None = Field(None, description="Optional difficulty indicator")
    mastery: float | None = Field(None, description="Current mastery score in [0,1]")
    next_review_at: datetime | None = Field(None, description="Next scheduled review timestamp")
    exposures: int = Field(0, description="Total review exposures")
    lesson_id: UUID | None = Field(None, description="Deterministic lesson ID mapped to this concept")
    lesson_id_ref: UUID | None = Field(None, description="Alias for lesson ID reference")
    prerequisites: list[UUID] = Field(default_factory=list, description="List of prerequisite concept IDs")
    order: int | None = Field(None, description="Ordering hint within course graph")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class FrontierResponse(BaseModel):
    """Response payload for adaptive concept frontier."""

    frontier: list[ConceptSummary] = Field(default_factory=list, description="Unlocked concepts ready for learning")
    due_for_review: list[ConceptSummary] = Field(default_factory=list, description="Concepts due for review")
    coming_soon: list[ConceptSummary] = Field(default_factory=list, description="Locked concepts close to unlocking")
    due_count: int = Field(0, description="Number of concepts currently due")
    avg_mastery: float = Field(0.0, description="Average mastery across course concepts")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ReviewRequest(BaseModel):
    """Single concept review submission."""

    concept_id: UUID = Field(..., description="Concept being reviewed")
    rating: int = Field(..., ge=1, le=4, description="Review quality rating (1-4)")
    review_duration_ms: int = Field(..., ge=0, description="Duration spent reviewing in milliseconds")
    latency_ms: int | None = Field(None, ge=0, description="Optional latency before answering in milliseconds")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ReviewBatchRequest(BaseModel):
    """Batch review payload."""

    reviews: list[ReviewRequest] = Field(..., min_length=1, description="List of concept reviews")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ReviewOutcome(BaseModel):
    """Per-concept outcome returned after submitting reviews."""

    concept_id: UUID = Field(..., description="Reviewed concept ID")
    next_review_at: datetime | None = Field(None, description="Scheduled next review timestamp")
    mastery: float | None = Field(None, description="Updated mastery score")
    exposures: int = Field(0, description="Total exposures after update")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ReviewBatchResponse(BaseModel):
    """Response for review submissions."""

    outcomes: list[ReviewOutcome] = Field(default_factory=list, description="Per-concept scheduling outcomes")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class NextReviewResponse(BaseModel):
    """Response for concept next-review lookup."""

    concept_id: UUID = Field(..., description="Concept ID")
    next_review_at: datetime | None = Field(None, description="Next review timestamp")
    current_mastery: float | None = Field(None, description="Current mastery score")
    total_exposures: int = Field(0, description="Total exposures for the concept")

    model_config = ConfigDict(**_CAMEL_CONFIG)


GradeKind = str
GradeStatus = Literal["correct", "incorrect", "parse_error", "unsupported"]
PracticeContext = Literal["inline", "quick_check", "scheduled_review", "drill"]


class GradeExpectedPayload(BaseModel):
    """Expected answer payload for grading."""

    expected_latex: str = Field(..., min_length=1, description="Expected answer in LaTeX")
    criteria: str | None = Field(None, description="Optional grading criteria or simplification note")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeAnswerPayload(BaseModel):
    """Learner answer payload for grading."""

    answer_latex: str = Field(..., min_length=1, description="Learner answer in LaTeX")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeContextPayload(BaseModel):
    """Context payload for grading to enable adaptive wiring."""

    course_id: UUID = Field(..., description="Course ID for the practice interaction")
    lesson_id: UUID = Field(..., description="Lesson ID for the practice interaction")
    concept_id: UUID = Field(..., description="Concept ID used for adaptive scheduling")
    practice_context: PracticeContext = Field(..., description="Practice surface that collected the answer")
    hints_used: int | None = Field(
        None,
        ge=0,
        description="Number of hints revealed before submission",
    )

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeRequest(BaseModel):
    """Request payload for grading a learner response."""

    kind: GradeKind = Field(..., description="Answer kind to grade")
    question: str = Field(..., min_length=1, description="Learner-facing question prompt")
    expected: GradeExpectedPayload = Field(..., description="Expected answer payload")
    answer: GradeAnswerPayload = Field(..., description="Learner-provided answer payload")
    context: GradeContextPayload = Field(..., description="Context for adaptive learning signals")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class VerifierInfo(BaseModel):
    """Verifier metadata attached to grading responses."""

    name: str = Field(..., description="Verifier name")
    method: str | None = Field(None, description="Verification method used to determine correctness")
    notes: str | None = Field(None, description="Optional notes about the verification process")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GradeErrorHighlight(BaseModel):
    """Optional highlight for focused feedback in grading responses."""

    latex: str = Field(..., min_length=1, description="LaTeX fragment to emphasize")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeResponse(BaseModel):
    """Response payload for grading requests."""

    is_correct: bool = Field(..., description="Deterministic correctness flag from verifier")
    status: GradeStatus = Field(..., description="Verification status")
    feedback_markdown: str = Field(..., min_length=1, description="Feedback rendered to learners (Markdown)")
    verifier: VerifierInfo = Field(..., description="Verifier metadata")
    tags: list[str] = Field(default_factory=list, description="Optional diagnostic tags for analytics")
    error_highlight: GradeErrorHighlight | None = Field(
        None,
        description="Optional LaTeX fragment to highlight for targeted feedback",
    )

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ExecutionFilePayload(BaseModel):
    """Single workspace file included during execution."""

    path: str = Field(..., min_length=1, description="Relative path of the file inside the workspace root")
    content: str = Field(..., description="Full file contents written to the sandbox before execution")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CodeExecuteRequest(BaseModel):
    """Request to execute a code snippet via E2B."""

    code: str = Field(..., min_length=1, description="Source code to execute")
    language: str = Field(..., min_length=1, description="Language name/alias, e.g., python, js, cpp")
    stdin: str | None = Field(None, description="Optional stdin input")
    lesson_id: UUID | None = Field(None, description="Optional lesson id for analytics/logging")
    course_id: UUID | None = Field(None, description="Course id for sandbox scoping and setup commands")
    files: list[ExecutionFilePayload] | None = Field(None, description="Optional multi-file workspace payload")
    entry_file: str | None = Field(None, description="Entry file path to run when workspace files are provided")
    workspace_id: str | None = Field(None, description="Logical workspace identifier for grouping files")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CodeExecuteResponse(BaseModel):
    """Normalized execution response payload."""

    stdout: str | None = None
    stderr: str | None = None
    status: str | None = None
    time: float | None = None
    memory: float | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)
