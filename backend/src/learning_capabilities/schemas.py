"""Typed contracts for learning capability inputs/outputs."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.config.schema_casing import to_camel


_CAMEL_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)

CapabilityKind = Literal["read", "write", "generation"]
ContextType = Literal["book", "video", "course"]
CourseMode = Literal["adaptive", "standard"]
ConceptMatchSource = Literal["embedding", "lexical"]
CourseSourceType = Literal["course_document"]
TutorCauseKind = Literal["current_concept", "recent_miss", "prerequisite_gap", "semantic_confusor"]
TutorCauseSource = Literal["course_context", "probe_event", "concept_graph", "concept_similarity"]
TutorMove = Literal[
    "answer",
    "hint",
    "probe",
    "articulate",
    "reflect",
    "contrast_confusion",
    "review",
    "route_to_lesson",
    "defer",
]


def _default_course_source_types() -> list[CourseSourceType]:
    return ["course_document"]


def _default_tutor_moves() -> list[TutorMove]:
    return [
        "answer",
        "hint",
        "probe",
        "articulate",
        "reflect",
        "contrast_confusion",
        "review",
        "route_to_lesson",
        "defer",
    ]


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


class CourseSourceExcerpt(BaseModel):
    """Compact course-source excerpt for assistant grounding."""

    course_id: uuid.UUID
    source_type: CourseSourceType = "course_document"
    title: str | None = None
    excerpt: str
    similarity: float
    chunk_id: str
    document_id: int | None = None
    chunk_index: int | None = None
    total_chunks: int | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class SourceFocus(BaseModel):
    """Tiny auto-source focus for course-grounded chat."""

    course_id: uuid.UUID
    items: list[CourseSourceExcerpt] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ActiveProbeSuggestion(BaseModel):
    """Compact signal that a chat probe may be useful now."""

    course_id: uuid.UUID
    concept_id: uuid.UUID
    lesson_id: uuid.UUID | None = None
    learner_asked_check: bool = False
    learner_expressed_uncertainty: bool = False
    learner_shared_reasoning: bool = False
    repeated_recent_misses: bool = False

    model_config = ConfigDict(**_CAMEL_CONFIG)


class LessonWindowState(BaseModel):
    """Window-level lesson content for assistant grounding."""

    window_id: uuid.UUID
    lesson_id: uuid.UUID
    version_id: uuid.UUID
    window_index: int
    title: str | None = None
    content: str
    estimated_minutes: int

    model_config = ConfigDict(**_CAMEL_CONFIG)


class RecentProbeSignal(BaseModel):
    """Recent probe outcome for tutor debugging context."""

    probe_id: uuid.UUID
    concept_id: uuid.UUID
    correct: bool
    occurred_at: datetime
    tags: list[str] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class TutorEvidenceSignals(BaseModel):
    """Deterministic evidence-quality signals for cautious tutoring."""

    recent_probe_count: int = 0
    recent_correct_count: int = 0
    mastery_evidence_count: int = 0
    last_probe_at: datetime | None = None
    state_updated_at: datetime | None = None
    has_sparse_evidence: bool = True
    has_stale_evidence: bool = False

    model_config = ConfigDict(**_CAMEL_CONFIG)


class TutorCandidateCause(BaseModel):
    """Possible tutoring cause, not a diagnosis."""

    rank: int
    kind: TutorCauseKind
    concept_id: uuid.UUID
    source: TutorCauseSource

    model_config = ConfigDict(**_CAMEL_CONFIG)


class TutorDeterministicSignals(BaseModel):
    """Simple booleans and counts the prompt can reason over."""

    has_prerequisite_gap: bool = False
    has_recent_miss: bool = False
    due: bool = False
    has_semantic_confusor: bool = False
    exposures: int = 0
    recent_probe_count: int = 0
    recent_correct_count: int = 0
    mastery_evidence_count: int = 0

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


class SearchCourseSourcesCapabilityInput(BaseModel):
    """Input payload for course-source search capability."""

    course_id: uuid.UUID
    query: str = Field(..., min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    source_types: list[CourseSourceType] = Field(default_factory=_default_course_source_types)

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GetLessonWindowsCapabilityInput(BaseModel):
    """Input payload for lesson-window lookup capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    window_index: int | None = Field(default=None, ge=0)
    limit: int = Field(default=3, ge=1, le=10)

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GetConceptTutorContextCapabilityInput(BaseModel):
    """Input payload for adaptive concept tutor context."""

    course_id: uuid.UUID
    concept_id: uuid.UUID
    include_recent_probes: bool = True
    include_lesson_summary: bool = True

    model_config = ConfigDict(extra="forbid", **_CAMEL_CONFIG)


class GenerateConceptProbeCapabilityInput(BaseModel):
    """Input payload for chat concept probe generation."""

    course_id: uuid.UUID
    concept_id: uuid.UUID
    count: int = Field(default=1, ge=1, le=1)
    practice_context: Literal["chat"] = "chat"
    learner_context: str | None = Field(default=None, max_length=2000)
    thread_id: uuid.UUID | None = None

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


class SearchCourseSourcesCapabilityOutput(BaseModel):
    """Output payload for course-source search capability."""

    course_id: uuid.UUID
    items: list[CourseSourceExcerpt] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GetLessonWindowsCapabilityOutput(BaseModel):
    """Output payload for lesson-window lookup capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    version_id: uuid.UUID | None = None
    items: list[LessonWindowState] = Field(default_factory=list)

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GetConceptTutorContextCapabilityOutput(BaseModel):
    """Output payload for adaptive concept tutor context."""

    course_id: uuid.UUID
    course_mode: CourseMode
    concept_id: uuid.UUID | None = None
    concept_name: str | None = None
    description: str | None = None
    difficulty: float | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    mastery: float | None = None
    exposures: int = 0
    next_review_at: datetime | None = None
    due: bool = False
    learner_profile: LearnerProfileSignals | None = None
    recent_probes: list[RecentProbeSignal] = Field(default_factory=list)
    prerequisite_gaps: list[ConceptRelationSignal] = Field(default_factory=list)
    semantic_confusors: list[ConceptRelationSignal] = Field(default_factory=list)
    downstream_blocked: list[ConceptRelationSignal] = Field(default_factory=list)
    has_verified_content: bool = False
    content_source_count: int = 0
    evidence: TutorEvidenceSignals = Field(default_factory=TutorEvidenceSignals)
    candidate_causes: list[TutorCandidateCause] = Field(default_factory=list)
    deterministic_signals: TutorDeterministicSignals = Field(default_factory=TutorDeterministicSignals)
    allowed_tutor_moves: list[TutorMove] = Field(default_factory=_default_tutor_moves)
    reason: str | None = None

    model_config = ConfigDict(**_CAMEL_CONFIG)


class ChatConceptProbe(BaseModel):
    """Learner-visible active chat probe."""

    active_probe_id: uuid.UUID
    question: str
    answer_kind: str
    hints: list[str] = Field(default_factory=list)
    course_id: uuid.UUID
    concept_id: uuid.UUID
    lesson_id: uuid.UUID

    model_config = ConfigDict(**_CAMEL_CONFIG)


class GenerateConceptProbeCapabilityOutput(BaseModel):
    """Output payload for chat concept probe generation."""

    course_id: uuid.UUID
    course_mode: CourseMode
    concept_id: uuid.UUID
    active_probe_id: uuid.UUID | None = None
    probe: ChatConceptProbe | None = None
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
    source_focus: SourceFocus | None = None
    active_probe_suggestion: ActiveProbeSuggestion | None = None
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
