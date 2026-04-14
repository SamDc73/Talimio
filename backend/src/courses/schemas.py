
"""Pydantic schemas for the unified courses API."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.config.schema_casing import to_camel


_CAMEL_CONFIG = {"alias_generator": to_camel, "populate_by_name": True}


class LessonSummary(BaseModel):
    """Lightweight lesson representation for course outlines."""

    id: uuid.UUID = Field(..., description="Lesson ID")
    title: str = Field(..., description="Lesson title")
    description: str | None = Field(None, description="Lesson description")
    order: int = Field(..., description="Lesson order within its module")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class LessonVersionSummary(BaseModel):
    """Compact version metadata for lesson history UI."""

    id: uuid.UUID = Field(..., description="Lesson version ID")
    major_version: int = Field(..., description="Major version number")
    minor_version: int = Field(..., description="Minor version number")
    version_kind: str = Field(..., description="Version kind label")
    version_label: str = Field(..., description="Display label such as 1.0")
    pass_label: str | None = Field(None, description="Lightweight pass label such as Pass 2")
    history_label: str | None = Field(None, description="Short history label such as Regenerated")
    source_reason: str | None = Field(None, description="Why this version exists")
    is_current: bool = Field(..., description="Whether this is the current active version")
    created_at: datetime = Field(..., description="Version creation timestamp")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonWindowResponse(BaseModel):
    """Window payload for segmented lesson delivery."""

    id: uuid.UUID = Field(..., description="Lesson window ID")
    window_index: int = Field(..., description="Zero-based window index")
    title: str | None = Field(None, description="Optional window title")
    content: str = Field(..., description="Window content")
    estimated_minutes: int = Field(..., description="Estimated reading time in minutes")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonNextPassResponse(BaseModel):
    """Lightweight metadata for the next major lesson pass."""

    major_version: int = Field(..., description="Next major version number")
    pass_label: str = Field(..., description="User-facing label such as Pass 2")
    status: Literal["recommended_now", "available_early"] = Field(
        ...,
        description="Whether the next pass is recommended now or only available as an early override",
    )
    reason: str = Field(..., description="Short explanation for the next-pass recommendation state")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonDetailResponse(BaseModel):
    """Schema for detailed lesson responses (content endpoint)."""

    id: uuid.UUID = Field(..., description="Lesson ID")
    course_id: uuid.UUID = Field(..., description="Course ID")
    title: str = Field(..., description="Lesson title")
    description: str | None = Field(None, description="Lesson description")
    content: str | None = Field(None, description="Lesson content (MDX format)")
    concept_id: uuid.UUID | None = Field(None, description="Mapped concept ID for adaptive lessons")
    version_id: uuid.UUID | None = Field(None, description="Selected lesson version ID")
    current_version_id: uuid.UUID | None = Field(None, description="Current active lesson version ID")
    major_version: int | None = Field(None, description="Selected lesson major version")
    minor_version: int | None = Field(None, description="Selected lesson minor version")
    version_kind: str | None = Field(None, description="Selected lesson version kind")
    version_label: str | None = Field(None, description="Selected lesson version label")
    pass_label: str | None = Field(None, description="Selected lesson pass label")
    source_reason: str | None = Field(None, description="Why the selected version exists")
    available_versions: list[LessonVersionSummary] = Field(
        default_factory=list,
        description="Available version history for this lesson",
    )
    next_pass: LessonNextPassResponse | None = Field(
        None,
        description="Lightweight next-major-pass metadata for the current active lesson view",
    )
    windows: list[LessonWindowResponse] = Field(default_factory=list, description="Windowed lesson delivery payload")
    adaptive_enabled: bool | None = Field(None, description="Whether the parent course is adaptive")
    created_at: datetime = Field(..., description="Lesson creation timestamp")
    updated_at: datetime = Field(..., description="Lesson last update timestamp")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class LessonVersionHistoryResponse(BaseModel):
    """Response payload for lesson version history."""

    versions: list[LessonVersionSummary] = Field(default_factory=list, description="Available lesson versions")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonRegenerateRequest(BaseModel):
    """Request payload for explicit lesson regeneration."""

    critique_text: str = Field(..., min_length=1, description="What the learner wants changed in the lesson")
    apply_across_course: bool = Field(
        default=False,
        description="Whether this critique should influence future lessons",
    )

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class LessonNextPassRequest(BaseModel):
    """Request payload for starting the next major lesson pass."""

    force: bool = Field(
        default=False,
        description="Whether to allow an early override even when the next pass is usually recommended later",
    )

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class CourseBase(BaseModel):
    """Base schema for courses."""

    title: str = Field(..., description="Course title", max_length=200)
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

    title: str | None = Field(None, description="Course title", max_length=200)
    description: str | None = Field(None, description="Course description")
    tags: str | None = Field(None, description="Course tags as JSON string")
    archived: bool | None = Field(None, description="Whether the course is archived")
    adaptive_enabled: bool | None = Field(None, description="Enable or disable adaptive scheduling")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ModuleResponse(BaseModel):
    """Schema for synthesized module responses."""

    id: uuid.UUID = Field(..., description="Module ID")
    title: str = Field(..., description="Module title")
    description: str | None = Field(None, description="Module description")
    lessons: list[LessonSummary] = Field(default_factory=list, description="Module lessons")

    model_config = ConfigDict(from_attributes=True, **_CAMEL_CONFIG)


class CourseResponse(CourseBase):
    """Schema for course responses."""

    id: uuid.UUID = Field(..., description="Course ID")
    user_id: uuid.UUID | None = Field(None, description="Owner user ID")
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

    id: uuid.UUID = Field(..., description="Concept ID")
    name: str = Field(..., description="Concept display name")
    description: str = Field(..., description="Concept description")
    difficulty: int | None = Field(None, description="Optional difficulty indicator")
    mastery: float | None = Field(None, description="Current mastery score in [0,1]")
    next_review_at: datetime | None = Field(None, description="Next scheduled review timestamp")
    exposures: int = Field(0, description="Total review exposures")
    lesson_id: uuid.UUID | None = Field(None, description="Lesson ID linked to this concept")
    recommended_lesson_entry: Literal["open_current", "start_next_pass"] | None = Field(
        None,
        description="Backend-owned adaptive lesson entry recommendation for this concept",
    )
    prerequisites: list[uuid.UUID] = Field(default_factory=list, description="List of prerequisite concept IDs")
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

    concept_id: uuid.UUID = Field(..., description="Concept being reviewed")
    question: str | None = Field(
        None,
        min_length=1,
        description="Optional learner-facing prompt text used for duplicate detection in practice generation",
    )
    rating: int = Field(..., ge=1, le=4, description="Review quality rating (1-4)")
    review_duration_ms: int = Field(..., ge=0, description="Duration spent reviewing in milliseconds")
    latency_ms: int | None = Field(None, ge=0, description="Optional latency before answering in milliseconds")
    structure_signature: str | None = Field(
        None,
        min_length=1,
        description="Optional question structure signature used for practice duplicate/cadence analysis",
    )
    predicted_p_correct: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional model-estimated probability of correctness for this probe",
    )
    core_model: str | None = Field(
        None,
        min_length=1,
        description="Optional provider/model id used to generate the practice question",
    )
    target_probability: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional target probability used during drill selection",
    )
    target_low: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional lower bound for the drill target band",
    )
    target_high: float | None = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Optional upper bound for the drill target band",
    )

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ReviewBatchRequest(BaseModel):
    """Batch review payload."""

    reviews: list[ReviewRequest] = Field(..., min_length=1, description="List of concept reviews")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ReviewOutcome(BaseModel):
    """Per-concept outcome returned after submitting reviews."""

    concept_id: uuid.UUID = Field(..., description="Reviewed concept ID")
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

    concept_id: uuid.UUID = Field(..., description="Concept ID")
    next_review_at: datetime | None = Field(None, description="Next review timestamp")
    current_mastery: float | None = Field(None, description="Current mastery score")
    total_exposures: int = Field(0, description="Total exposures for the concept")

    model_config = ConfigDict(**_CAMEL_CONFIG)


GradeKind = Literal["latex_expression", "jxg_state", "practice_answer"]
GradeStatus = Literal["correct", "incorrect", "parse_error", "unsupported"]
PracticeContext = Literal["inline", "quick_check", "scheduled_review", "drill"]
PracticeAnswerKind = Literal["math_latex", "text"]


class JXGBoardState(BaseModel):
    """Normalized board state used for deterministic JSXGraph grading."""

    points: dict[str, tuple[float, float]] = Field(
        default_factory=dict,
        description=(
            "Point coordinates keyed by stable point id (use explicit JSXGraph `name`, for example `A`) "
            "with values `[x, y]`"
        ),
    )
    sliders: dict[str, float] = Field(
        default_factory=dict,
        description="Slider values keyed by stable slider id (use explicit JSXGraph `name`, for example `a`)",
    )
    curves: dict[str, list[tuple[float, float]]] = Field(
        default_factory=dict,
        description=(
            "Curve samples keyed by stable curve id. Values must be fixed ordered samples `[[x1,y1], ...]` "
            "that can be compared by index against expected samples."
        ),
    )

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeExpectedPayload(BaseModel):
    """Expected answer payload for grading."""

    expected_latex: str | None = Field(None, min_length=1, description="Expected answer in LaTeX")
    expected_answer: str | None = Field(None, min_length=1, description="Expected answer for generalized practice grading")
    answer_kind: PracticeAnswerKind | None = Field(None, description="Expected answer type for generalized practice grading")
    expected_state: JXGBoardState | None = Field(
        None,
        description=(
            "Expected board state for JSXGraph grading using `{ points, sliders, curves }` shape "
            "with stable ids from JSXGraph `name`."
        ),
    )
    tolerance: float | None = Field(
        None,
        ge=0,
        description="Global tolerance used for graph-state comparisons",
    )
    per_check_tolerance: dict[str, float] | None = Field(
        None,
        description="Per-check tolerance overrides keyed by check id (`point:A`, `slider:a`, `curve:f`)",
    )
    criteria: str | None = Field(None, description="Optional grading criteria or simplification note")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeAnswerPayload(BaseModel):
    """Learner answer payload for grading."""

    answer_latex: str | None = Field(None, min_length=1, description="Learner answer in LaTeX")
    answer_text: str | None = Field(None, min_length=1, description="Learner answer string for generalized practice grading")
    answer_state: JXGBoardState | None = Field(
        None,
        description=(
            "Learner board state for JSXGraph grading using `{ points, sliders, curves }` and the same stable ids "
            "as expectedState."
        ),
    )

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GradeContextPayload(BaseModel):
    """Context payload for grading to enable adaptive wiring."""

    course_id: uuid.UUID = Field(..., description="Course ID for the practice interaction")
    lesson_id: uuid.UUID = Field(..., description="Lesson ID for the practice interaction")
    concept_id: uuid.UUID = Field(..., description="Concept ID used for adaptive scheduling")
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

    @model_validator(mode="after")
    def validate_payload_for_kind(self) -> GradeRequest:
        """Validate required payload fields for each grading kind."""
        if self.kind == "latex_expression":
            if not self.expected.expected_latex:
                message = "expected.expectedLatex is required when kind=latex_expression"
                raise ValueError(message)
            if not self.answer.answer_latex:
                message = "answer.answerLatex is required when kind=latex_expression"
                raise ValueError(message)
            return self

        if self.kind == "jxg_state":
            if self.expected.expected_state is None:
                message = "expected.expectedState is required when kind=jxg_state"
                raise ValueError(message)
            if self.answer.answer_state is None:
                message = "answer.answerState is required when kind=jxg_state"
                raise ValueError(message)
            return self

        if self.kind == "practice_answer":
            if not self.expected.expected_answer:
                message = "expected.expectedAnswer is required when kind=practice_answer"
                raise ValueError(message)
            if not self.expected.answer_kind:
                message = "expected.answerKind is required when kind=practice_answer"
                raise ValueError(message)
            if not self.answer.answer_text:
                message = "answer.answerText is required when kind=practice_answer"
                raise ValueError(message)
            return self

        return self


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
    feedback_metadata: dict[str, Any] | None = Field(
        None,
        description="Optional structured metadata with verifier deltas (for example deltaX, deltaY, off-by info)",
    )

    model_config = ConfigDict(**_CAMEL_CONFIG)


class PracticeDrillRequest(BaseModel):
    """Request payload for adaptive practice drill generation."""

    concept_id: uuid.UUID = Field(..., description="Concept to generate drill questions for")
    count: int = Field(..., ge=1, le=10, description="Number of drill items to generate")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class PracticeDrillItem(BaseModel):
    """Single generated practice drill item."""

    concept_id: uuid.UUID = Field(..., description="Concept this drill belongs to")
    lesson_id: uuid.UUID = Field(..., description="Lesson ID linked to this concept")
    question: str = Field(..., min_length=1, description="Learner-facing drill question")
    expected_answer: str = Field(..., min_length=1, description="Expected answer string")
    answer_kind: PracticeAnswerKind = Field(..., description="Expected answer input mode")
    hints: list[str] = Field(default_factory=list, description="Optional hints for this drill")
    structure_signature: str = Field(..., min_length=1, description="Normalized structural signature for duplicate checks")
    predicted_p_correct: float = Field(..., ge=0.0, le=1.0, description="Estimated correctness probability used for selection")
    target_probability: float = Field(..., ge=0.0, le=1.0, description="Target probability used to rank candidate drills")
    target_low: float = Field(..., ge=0.0, le=1.0, description="Lower bound of the target probability band")
    target_high: float = Field(..., ge=0.0, le=1.0, description="Upper bound of the target probability band")
    core_model: str = Field(..., min_length=1, description="Core model used to generate and rank the drill")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class PracticeDrillResponse(BaseModel):
    """Response payload for adaptive practice drill generation."""

    drills: list[PracticeDrillItem] = Field(default_factory=list, description="Generated drill items")

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


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
    lesson_id: uuid.UUID | None = Field(None, description="Optional lesson id for analytics/logging")
    course_id: uuid.UUID | None = Field(None, description="Course id for sandbox scoping and setup commands")
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


class RuntimeProcessStartRequest(BaseModel):
    """Start a long-lived runtime process in a scoped sandbox session."""

    command: str = Field(..., min_length=1)
    course_id: uuid.UUID | None = None
    workspace_id: str | None = None
    cwd: str | None = None
    env: dict[str, str] | None = None
    user: str | None = Field(default="user")

    model_config = ConfigDict(**_CAMEL_CONFIG)


class RuntimeProcessReadRequest(BaseModel):
    """Read process output for a scoped runtime process."""

    process_id: int = Field(..., ge=1)
    course_id: uuid.UUID | None = None
    workspace_id: str | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class RuntimeProcessInputRequest(BaseModel):
    """Send stdin data to a scoped runtime process."""

    process_id: int = Field(..., ge=1)
    input: str = Field(...)
    course_id: uuid.UUID | None = None
    workspace_id: str | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class RuntimeProcessStopRequest(BaseModel):
    """Stop a scoped runtime process."""

    process_id: int = Field(..., ge=1)
    course_id: uuid.UUID | None = None
    workspace_id: str | None = None
    wait_timeout_seconds: float | None = Field(default=None, ge=0)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class RuntimeListRequest(BaseModel):
    """List runtime filesystem entries for a scoped sandbox session."""

    path: str = Field(default=".")
    depth: int = Field(default=2, ge=1, le=10)
    course_id: uuid.UUID | None = None
    workspace_id: str | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class RuntimeToolResponse(BaseModel):
    """Generic runtime tool response payload."""

    data: dict[str, Any]

    model_config = ConfigDict(**_CAMEL_CONFIG)
