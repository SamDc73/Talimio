"""Typed contracts for learning capability inputs/outputs."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.config.schema_casing import to_camel


_CAMEL_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)

CapabilityKind = Literal["read", "write"]
ContextType = Literal["book", "video", "course"]
CourseMode = Literal["adaptive", "standard"]
ConceptMatchSource = Literal["embedding", "lexical"]


class CapabilityDescriptor(BaseModel):
    """Runtime metadata describing one capability."""

    name: str = Field(..., min_length=1)
    kind: CapabilityKind
    requires_confirmation: bool = False
    public_api_eligible: bool = True
    description: str = Field(..., min_length=1)

    model_config = ConfigDict(frozen=True, **_CAMEL_CONFIG)


class ToolUiLink(BaseModel):
    """Clickable navigation affordance for the chat UI."""

    type: Literal["link"] = "link"
    label: str = Field(..., min_length=1)
    href: str = Field(..., min_length=1)

    model_config = ConfigDict(frozen=True, **_CAMEL_CONFIG)


class ToolUiConfirmation(BaseModel):
    """Confirmation affordance for mutating tools."""

    type: Literal["confirmation"] = "confirmation"
    title: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    action_name: str = Field(..., min_length=1)
    confirm_label: str = Field(default="Confirm", min_length=1)
    cancel_label: str = Field(default="Cancel", min_length=1)

    model_config = ConfigDict(frozen=True, **_CAMEL_CONFIG)


class CourseMatch(BaseModel):
    """Compact course match payload for assistant routing/context."""

    id: uuid.UUID
    title: str
    description: str
    adaptive_enabled: bool
    completion_percentage: float = 0.0

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CourseState(BaseModel):
    """Compact learner-facing course state packet."""

    course_id: uuid.UUID
    title: str
    description: str
    adaptive_enabled: bool
    completion_percentage: float = 0.0
    total_lessons: int = 0
    completed_lessons: list[uuid.UUID] = Field(default_factory=list)
    current_lesson_id: uuid.UUID | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CourseCatalogEntry(BaseModel):
    """Compact home-surface course catalog entry."""

    course_id: uuid.UUID
    title: str
    adaptive_enabled: bool = False

    model_config = ConfigDict(**_CAMEL_CONFIG)


class AdaptiveCatalogEntry(BaseModel):
    """Compact adaptive summary entry for the home surface."""

    course_id: uuid.UUID
    title: str
    completion_percentage: float = 0.0
    current_lesson_id: uuid.UUID | None = None
    current_lesson_title: str | None = None
    due_count: int = 0
    avg_mastery: float = 0.0

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CourseOutlineLessonState(BaseModel):
    """Minimal per-lesson routing state for one course outline."""

    lesson_id: uuid.UUID
    title: str
    description: str | None = None
    module_name: str | None = None
    module_order: int | None = None
    order: int = 0
    has_content: bool = False
    completed: bool = False
    is_current: bool = False

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CourseOutlineState(BaseModel):
    """Compact course outline packet for assistant routing."""

    course_id: uuid.UUID
    lessons: list[CourseOutlineLessonState] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonState(BaseModel):
    """Compact lesson state packet."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    title: str
    description: str | None = None
    content: str | None = None
    has_content: bool = False
    module_name: str | None = None
    module_order: int | None = None
    order: int = 0

    model_config = ConfigDict(**_CAMEL_CONFIG)


class FrontierConceptState(BaseModel):
    """Concept row in compact frontier payloads."""

    concept_id: uuid.UUID
    lesson_id: uuid.UUID | None = None
    name: str
    mastery: float | None = None
    exposures: int = 0
    next_review_at: datetime | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CourseFrontierState(BaseModel):
    """Compact course frontier state packet."""

    due_count: int = 0
    avg_mastery: float = 0.0
    frontier: list[FrontierConceptState] = Field(default_factory=list)
    due_for_review: list[FrontierConceptState] = Field(default_factory=list)
    coming_soon: list[FrontierConceptState] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LearnerProfileSignals(BaseModel):
    """Raw per-concept learner profile signals."""

    success_rate: float | None = None
    retention_rate: float | None = None
    learning_speed: float | None = None
    semantic_sensitivity: float | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ConceptRelationSignal(BaseModel):
    """Compact related-concept signal for confusors and prerequisite gaps."""

    concept_id: uuid.UUID
    name: str
    similarity: float | None = None
    mastery: float | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class FocusedConceptState(BaseModel):
    """Concept state for the current lesson focus."""

    concept_id: uuid.UUID
    name: str
    description: str | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    mastery: float | None = None
    exposures: int = 0
    next_review_at: datetime | None = None
    due: bool = False
    confusors: list[ConceptRelationSignal] = Field(default_factory=list)
    prerequisite_gaps: list[ConceptRelationSignal] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ConceptMatch(FocusedConceptState):
    """Course-scoped concept match with raw ranking signals."""

    similarity: float | None = None
    match_score: float
    match_source: ConceptMatchSource
    candidate_rank: int
    score_gap_to_next: float | None = None


class ConceptFocus(BaseModel):
    """Adaptive-course concept focus for assistant routing."""

    current_lesson_concept: FocusedConceptState | None = None
    semantic_candidates: list[ConceptMatch] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonFocus(BaseModel):
    """Standard-course lesson focus without adaptive learner state."""

    lesson_id: uuid.UUID
    title: str
    description: str | None = None
    has_content: bool = False
    window_preview: str | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class SearchLessonsCapabilityInput(BaseModel):
    """Input payload for lesson search capability."""

    query: str = Field(..., min_length=1)
    course_id: uuid.UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class SearchConceptsCapabilityInput(BaseModel):
    """Input payload for adaptive course concept search."""

    query: str = Field(..., min_length=1)
    course_id: uuid.UUID
    limit: int = Field(default=5, ge=1, le=20)
    include_state: bool = True

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class LessonMatch(BaseModel):
    """Compact lesson search match row."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    course_title: str
    lesson_title: str
    lesson_description: str | None = None
    module_name: str | None = None
    order: int = 0

    model_config = ConfigDict(**_CAMEL_CONFIG)


class SearchLessonsCapabilityOutput(BaseModel):
    """Output payload for lesson search capability."""

    items: list[LessonMatch] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class SearchConceptsCapabilityOutput(BaseModel):
    """Output payload for adaptive course concept search."""

    course_id: uuid.UUID
    course_mode: CourseMode
    items: list[ConceptMatch] = Field(default_factory=list)
    reason: str | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ListRelevantCoursesCapabilityInput(BaseModel):
    """Input payload for relevant-course matching."""

    query: str = Field(..., min_length=1)
    limit: int = Field(default=6, ge=1, le=20)

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class ListRelevantCoursesCapabilityOutput(BaseModel):
    """Output payload for relevant-course matching."""

    items: list[CourseMatch] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GetCourseStateCapabilityInput(BaseModel):
    """Input payload for course state lookup."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GetCourseStateCapabilityOutput(BaseModel):
    """Output payload for course state lookup."""

    state: CourseState

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GetCourseOutlineStateCapabilityInput(BaseModel):
    """Input payload for course outline lookup."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GetCourseOutlineStateCapabilityOutput(BaseModel):
    """Output payload for course outline lookup."""

    state: CourseOutlineState

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GetLessonStateCapabilityInput(BaseModel):
    """Input payload for lesson state lookup."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    generate: bool = False

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GetLessonStateCapabilityOutput(BaseModel):
    """Output payload for lesson state lookup."""

    state: LessonState

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GetCourseFrontierCapabilityInput(BaseModel):
    """Input payload for course frontier lookup."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GetCourseFrontierCapabilityOutput(BaseModel):
    """Output payload for course frontier lookup."""

    state: CourseFrontierState

    model_config = ConfigDict(**_CAMEL_CONFIG)


class BuildContextBundleCapabilityInput(BaseModel):
    """Input payload for capability-backed context packet assembly."""

    context_type: ContextType | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, Any] = Field(default_factory=dict)
    latest_user_text: str = ""
    selected_quote: str | None = None

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class BuildContextBundleCapabilityOutput(BaseModel):
    """Output payload for capability-backed context packets."""

    app_surface: ContextType | None = None
    context_type: ContextType | None = None
    context_id: uuid.UUID | None = None
    selected_quote: str | None = None
    relevant_courses: list[CourseMatch] = Field(default_factory=list)
    course_catalog: list[CourseCatalogEntry] | None = None
    adaptive_catalog: list[AdaptiveCatalogEntry] | None = None
    course_state: CourseState | None = None
    course_mode: CourseMode | None = None
    learner_profile: LearnerProfileSignals | None = None
    concept_focus: ConceptFocus | None = None
    lesson_focus: LessonFocus | None = None
    course_outline: CourseOutlineState | None = None
    lesson_state: LessonState | None = None
    frontier_state: CourseFrontierState | None = None
    generated_at: datetime

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ActionStatusMixin(BaseModel):
    """Shared status fields for mutating capability outputs."""

    status: Literal["completed", "confirmation_required"]
    message: str = Field(..., min_length=1)
    tool_ui: list[ToolUiLink | ToolUiConfirmation] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class CreateCourseCapabilityInput(BaseModel):
    """Input payload for course creation capability."""

    prompt: str = Field(..., min_length=1)
    adaptive_enabled: bool = False
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class CreateCourseCapabilityOutput(ActionStatusMixin):
    """Output payload for course creation capability."""

    course_id: uuid.UUID | None = None
    title: str | None = None


class AppendCourseLessonCapabilityInput(BaseModel):
    """Input payload for course lesson append capability."""

    course_id: uuid.UUID
    lesson_title: str = Field(..., min_length=1)
    lesson_description: str | None = None
    module_name: str | None = None
    generate_content: bool = True
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class AppendCourseLessonCapabilityOutput(ActionStatusMixin):
    """Output payload for course lesson append capability."""

    course_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    content_generated: bool = False


class ExtendLessonWithContextCapabilityInput(BaseModel):
    """Input payload for lesson extension capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    context: str = Field(..., min_length=1)
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class RegenerateLessonWithContextCapabilityInput(BaseModel):
    """Input payload for lesson regeneration capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    context: str = Field(..., min_length=1)
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class LessonMutationCapabilityOutput(ActionStatusMixin):
    """Output payload for lesson extend/regenerate capabilities."""

    course_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    has_content: bool = False
