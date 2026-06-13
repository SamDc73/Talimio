"""Typed contracts for learning capability inputs/outputs."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field, JsonValue

from src.books.schemas import BookRagStatus
from src.config.schema_casing import CamelModel


CapabilityKind = Literal["read", "write", "generation"]
ContextType = Literal["book", "video", "course"]
CourseMode = Literal["adaptive", "standard"]
ConceptMatchSource = Literal["embedding", "lexical"]
CourseSourceType = Literal["book"]
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
    return ["book"]


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


class CapabilityDescriptor(CamelModel):
    """Runtime metadata describing one capability."""

    name: str = Field(min_length=1)
    kind: CapabilityKind
    requires_confirmation: bool = False
    public_api_eligible: bool = True
    description: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True)


class ToolUiLink(CamelModel):
    """Clickable navigation affordance for the chat UI."""

    type: Literal["link"] = "link"
    label: str = Field(min_length=1)
    href: str = Field(min_length=1)

    model_config = ConfigDict(frozen=True)


class ToolUiConfirmation(CamelModel):
    """Confirmation affordance for mutating tools."""

    type: Literal["confirmation"] = "confirmation"
    title: str = Field(min_length=1)
    message: str = Field(min_length=1)
    action_name: str = Field(min_length=1)
    confirm_label: str = Field(default="Confirm", min_length=1)
    cancel_label: str = Field(default="Cancel", min_length=1)

    model_config = ConfigDict(frozen=True)


class CourseMatch(CamelModel):
    """Compact course match payload for assistant routing/context."""

    id: uuid.UUID
    title: str
    description: str
    adaptive_enabled: bool
    archived: bool = False
    completion_percentage: float = 0.0


class CourseState(CamelModel):
    """Compact learner-facing course state packet."""

    course_id: uuid.UUID
    title: str
    description: str
    adaptive_enabled: bool
    archived: bool = False
    completion_percentage: float = 0.0
    total_lessons: int = 0
    completed_lessons: list[uuid.UUID] = Field(default_factory=list)
    current_lesson_id: uuid.UUID | None = None


class CourseCatalogEntry(CamelModel):
    """Compact home-surface course catalog entry."""

    course_id: uuid.UUID
    title: str
    adaptive_enabled: bool = False
    archived: bool = False


class AdaptiveCatalogEntry(CamelModel):
    """Compact adaptive summary entry for the home surface."""

    course_id: uuid.UUID
    title: str
    archived: bool = False
    completion_percentage: float = 0.0
    current_lesson_id: uuid.UUID | None = None
    current_lesson_title: str | None = None
    due_count: int = 0
    avg_mastery: float = 0.0


class CourseOutlineLessonState(CamelModel):
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


class CourseOutlineState(CamelModel):
    """Compact course outline packet for assistant routing."""

    course_id: uuid.UUID
    lessons: list[CourseOutlineLessonState] = Field(default_factory=list)


class LessonState(CamelModel):
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


class FrontierConceptState(CamelModel):
    """Concept row in compact frontier payloads."""

    concept_id: uuid.UUID
    lesson_id: uuid.UUID | None = None
    name: str
    mastery: float | None = None
    exposures: int = 0
    next_review_at: datetime | None = None


class CourseFrontierState(CamelModel):
    """Compact course frontier state packet."""

    due_count: int = 0
    avg_mastery: float = 0.0
    frontier: list[FrontierConceptState] = Field(default_factory=list)
    due_for_review: list[FrontierConceptState] = Field(default_factory=list)
    coming_soon: list[FrontierConceptState] = Field(default_factory=list)


class LearnerProfileSignals(CamelModel):
    """Raw per-concept learner profile signals."""

    success_rate: float | None = None
    retention_rate: float | None = None
    learning_speed: float | None = None
    semantic_sensitivity: float | None = None


class ConceptRelationSignal(CamelModel):
    """Compact related-concept signal for confusors and prerequisite gaps."""

    concept_id: uuid.UUID
    name: str
    similarity: float | None = None
    mastery: float | None = None


class FocusedConceptState(CamelModel):
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


class ConceptMatch(FocusedConceptState):
    """Course-scoped concept match with raw ranking signals."""

    similarity: float | None = None
    match_score: float
    match_source: ConceptMatchSource
    candidate_rank: int
    score_gap_to_next: float | None = None


class ConceptFocus(CamelModel):
    """Adaptive-course concept focus for assistant routing."""

    current_lesson_concept: FocusedConceptState | None = None
    semantic_candidates: list[ConceptMatch] = Field(default_factory=list)


class LessonFocus(CamelModel):
    """Standard-course lesson focus without adaptive learner state."""

    lesson_id: uuid.UUID
    title: str
    description: str | None = None
    has_content: bool = False
    window_preview: str | None = None


class CourseSourceExcerpt(CamelModel):
    """Compact course-source excerpt for assistant grounding."""

    course_id: uuid.UUID
    source_type: CourseSourceType = "book"
    title: str | None = None
    excerpt: str
    similarity: float
    chunk_id: str
    book_id: uuid.UUID | None = None
    chunk_index: int | None = None
    total_chunks: int | None = None


class SourceFocus(CamelModel):
    """Tiny auto-source focus for course-grounded chat."""

    course_id: uuid.UUID
    items: list[CourseSourceExcerpt] = Field(default_factory=list)


class ActiveProbeSuggestion(CamelModel):
    """Compact signal that a chat probe may be useful now."""

    course_id: uuid.UUID
    concept_id: uuid.UUID
    lesson_id: uuid.UUID | None = None
    learner_asked_check: bool = False
    learner_expressed_uncertainty: bool = False
    learner_shared_reasoning: bool = False
    repeated_recent_misses: bool = False


class LessonWindowState(CamelModel):
    """Window-level lesson content for assistant grounding."""

    window_id: uuid.UUID
    lesson_id: uuid.UUID
    version_id: uuid.UUID
    window_index: int
    title: str | None = None
    content: str
    estimated_minutes: int


class RecentProbeSignal(CamelModel):
    """Recent probe outcome for tutor debugging context."""

    probe_id: uuid.UUID
    concept_id: uuid.UUID
    correct: bool
    occurred_at: datetime
    tags: list[str] = Field(default_factory=list)


class TutorEvidenceSignals(CamelModel):
    """Deterministic evidence-quality signals for cautious tutoring."""

    recent_probe_count: int = 0
    recent_correct_count: int = 0
    mastery_evidence_count: int = 0
    last_probe_at: datetime | None = None
    state_updated_at: datetime | None = None
    has_sparse_evidence: bool = True
    has_stale_evidence: bool = False


class TutorCandidateCause(CamelModel):
    """Possible tutoring cause, not a diagnosis."""

    rank: int
    kind: TutorCauseKind
    concept_id: uuid.UUID
    source: TutorCauseSource


class TutorDeterministicSignals(CamelModel):
    """Simple booleans and counts the prompt can reason over."""

    has_prerequisite_gap: bool = False
    has_recent_miss: bool = False
    due: bool = False
    has_semantic_confusor: bool = False
    exposures: int = 0
    recent_probe_count: int = 0
    recent_correct_count: int = 0
    mastery_evidence_count: int = 0


class SearchLessonsCapabilityInput(CamelModel):
    """Input payload for lesson search capability."""

    query: str = Field(min_length=1)
    course_id: uuid.UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)

    model_config = ConfigDict(extra="forbid")


class SearchConceptsCapabilityInput(CamelModel):
    """Input payload for adaptive course concept search."""

    query: str = Field(min_length=1)
    course_id: uuid.UUID
    limit: int = Field(default=5, ge=1, le=20)
    include_state: bool = True

    model_config = ConfigDict(extra="forbid")


class SearchCourseSourcesCapabilityInput(CamelModel):
    """Input payload for course-source search capability."""

    course_id: uuid.UUID
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=20)
    source_types: list[CourseSourceType] = Field(default_factory=_default_course_source_types)

    model_config = ConfigDict(extra="forbid")


class GetLessonWindowsCapabilityInput(CamelModel):
    """Input payload for lesson-window lookup capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    window_index: int | None = Field(default=None, ge=0)
    limit: int = Field(default=3, ge=1, le=10)

    model_config = ConfigDict(extra="forbid")


class GetConceptTutorContextCapabilityInput(CamelModel):
    """Input payload for adaptive concept tutor context."""

    course_id: uuid.UUID
    concept_id: uuid.UUID
    include_recent_probes: bool = True
    include_lesson_summary: bool = True

    model_config = ConfigDict(extra="forbid")


class GenerateConceptProbeCapabilityInput(CamelModel):
    """Input payload for chat concept probe generation."""

    course_id: uuid.UUID
    concept_id: uuid.UUID
    count: int = Field(default=1, ge=1, le=1)
    practice_context: Literal["chat"] = "chat"
    learner_context: str | None = Field(default=None, max_length=2000)
    thread_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class LessonMatch(CamelModel):
    """Compact lesson search match row."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    course_title: str
    lesson_title: str
    lesson_description: str | None = None
    module_name: str | None = None
    order: int = 0


class SearchLessonsCapabilityOutput(CamelModel):
    """Output payload for lesson search capability."""

    items: list[LessonMatch] = Field(default_factory=list)


class SearchConceptsCapabilityOutput(CamelModel):
    """Output payload for adaptive course concept search."""

    course_id: uuid.UUID
    course_mode: CourseMode
    items: list[ConceptMatch] = Field(default_factory=list)
    reason: str | None = None


class SearchCourseSourcesCapabilityOutput(CamelModel):
    """Output payload for course-source search capability."""

    course_id: uuid.UUID
    items: list[CourseSourceExcerpt] = Field(default_factory=list)


class GetLessonWindowsCapabilityOutput(CamelModel):
    """Output payload for lesson-window lookup capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    version_id: uuid.UUID | None = None
    items: list[LessonWindowState] = Field(default_factory=list)


class GetConceptTutorContextCapabilityOutput(CamelModel):
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


class ChatConceptProbe(CamelModel):
    """Learner-visible active chat probe."""

    active_probe_id: uuid.UUID
    question: str
    answer_kind: str
    probe_family: str
    renderer_kind: str
    choices: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)
    course_id: uuid.UUID
    concept_id: uuid.UUID
    lesson_id: uuid.UUID


class ActiveChatProbe(CamelModel):
    """Assistant-visible active probe awaiting a learner answer."""

    active_probe_id: uuid.UUID
    course_id: uuid.UUID
    concept_id: uuid.UUID
    lesson_id: uuid.UUID
    question: str
    answer_kind: str
    probe_family: str
    renderer_kind: str
    choices: list[str] = Field(default_factory=list)
    hints: list[str] = Field(default_factory=list)


class GenerateConceptProbeCapabilityOutput(CamelModel):
    """Output payload for chat concept probe generation."""

    course_id: uuid.UUID
    course_mode: CourseMode
    concept_id: uuid.UUID
    active_probe_id: uuid.UUID | None = None
    probe: ChatConceptProbe | None = None
    reason: str | None = None


class SubmitConceptProbeResultCapabilityInput(CamelModel):
    """Input payload for submitting a chat-generated probe answer."""

    course_id: uuid.UUID
    active_probe_id: uuid.UUID | None = None
    learner_answer: str
    confirmed: bool = False
    thread_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None

    model_config = ConfigDict(extra="forbid")


class SubmitConceptProbeResultCapabilityOutput(CamelModel):
    """Output payload after grading and recording a chat probe answer."""

    course_id: uuid.UUID
    course_mode: CourseMode
    active_probe_id: uuid.UUID | None = None
    concept_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    is_correct: bool | None = None
    status: str | None = None
    feedback_markdown: str | None = None
    mastery: float | None = None
    exposures: int = 0
    next_review_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    reason: str | None = None


class ListRelevantCoursesCapabilityInput(CamelModel):
    """Input payload for relevant-course matching."""

    query: str = Field(min_length=1)
    limit: int = Field(default=6, ge=1, le=20)

    model_config = ConfigDict(extra="forbid")


class ListRelevantCoursesCapabilityOutput(CamelModel):
    """Output payload for relevant-course matching."""

    items: list[CourseMatch] = Field(default_factory=list)


class GetCourseStateCapabilityInput(CamelModel):
    """Input payload for course state lookup."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class GetCourseStateCapabilityOutput(CamelModel):
    """Output payload for course state lookup."""

    state: CourseState


class GetCourseOutlineStateCapabilityInput(CamelModel):
    """Input payload for course outline lookup."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class GetCourseOutlineStateCapabilityOutput(CamelModel):
    """Output payload for course outline lookup."""

    state: CourseOutlineState


class GetLessonStateCapabilityInput(CamelModel):
    """Input payload for lesson state lookup."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    generate: bool = False

    model_config = ConfigDict(extra="forbid")


class GetLessonStateCapabilityOutput(CamelModel):
    """Output payload for lesson state lookup."""

    state: LessonState


class GetCourseFrontierCapabilityInput(CamelModel):
    """Input payload for course frontier lookup."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class GetCourseFrontierCapabilityOutput(CamelModel):
    """Output payload for course frontier lookup."""

    state: CourseFrontierState


class BuildContextBundleCapabilityInput(CamelModel):
    """Input payload for capability-backed context packet assembly."""

    context_type: ContextType | None = None
    context_id: uuid.UUID | None = None
    context_meta: dict[str, JsonValue] = Field(default_factory=dict)
    latest_user_text: str = ""
    selected_quote: str | None = None

    model_config = ConfigDict(extra="forbid")


class BuildContextBundleCapabilityOutput(CamelModel):
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
    active_chat_probe: ActiveChatProbe | None = None
    course_outline: CourseOutlineState | None = None
    lesson_state: LessonState | None = None
    frontier_state: CourseFrontierState | None = None
    generated_at: datetime


class ActionStatusMixin(CamelModel):
    """Shared status fields for mutating capability outputs."""

    status: Literal["completed", "confirmation_required"]
    message: str = Field(min_length=1)
    tool_ui: list[ToolUiLink | ToolUiConfirmation] = Field(default_factory=list)


class BookMatch(CamelModel):
    """Compact book result for AI-facing book discovery.

    Carries archived and ragStatus flags; never filtered by them.
    """

    book_id: uuid.UUID
    title: str
    author: str | None = None
    archived: bool = False
    rag_status: BookRagStatus = "pending"
    excerpt: str | None = None
    similarity: float | None = None


class SearchBooksCapabilityInput(CamelModel):
    """Input payload for user-wide book search. No archived filter exists."""

    query: str = Field(min_length=1)
    limit: int = Field(default=8, ge=1, le=20)

    model_config = ConfigDict(extra="forbid")


class SearchBooksCapabilityOutput(CamelModel):
    """Output payload for user-wide book search."""

    items: list[BookMatch] = Field(default_factory=list)


class ListBooksCapabilityInput(CamelModel):
    """Input payload for listing every book the user owns."""

    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=50)

    model_config = ConfigDict(extra="forbid")


class ListBooksCapabilityOutput(CamelModel):
    """Output payload for the book listing capability."""

    items: list[BookMatch] = Field(default_factory=list)
    total: int = 0


class CourseAttachmentItem(CamelModel):
    """One course attachment with denormalized book fields."""

    id: uuid.UUID
    kind: Literal["book"] = "book"
    book_id: uuid.UUID
    title: str
    rag_status: BookRagStatus
    archived: bool
    created_at: datetime


class ListCourseAttachmentsCapabilityInput(CamelModel):
    """Input payload for listing one course's attachments."""

    course_id: uuid.UUID

    model_config = ConfigDict(extra="forbid")


class ListCourseAttachmentsCapabilityOutput(CamelModel):
    """Output payload for listing one course's attachments."""

    course_id: uuid.UUID
    items: list[CourseAttachmentItem] = Field(default_factory=list)


class AttachBookToCourseCapabilityInput(CamelModel):
    """Input payload for attaching books to a course."""

    course_id: uuid.UUID
    book_ids: list[uuid.UUID] = Field(min_length=1, max_length=50)
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid")


class AttachBookToCourseCapabilityOutput(ActionStatusMixin):
    """Output payload for attaching books to a course."""

    course_id: uuid.UUID | None = None
    attachments: list[CourseAttachmentItem] = Field(default_factory=list)


class DetachBookFromCourseCapabilityInput(CamelModel):
    """Input payload for detaching one book from a course."""

    course_id: uuid.UUID
    book_id: uuid.UUID
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid")


class DetachBookFromCourseCapabilityOutput(ActionStatusMixin):
    """Output payload for detaching one book from a course."""

    course_id: uuid.UUID | None = None
    book_id: uuid.UUID | None = None


class CreateCourseCapabilityInput(CamelModel):
    """Input payload for course creation capability."""

    prompt: str = Field(min_length=1)
    adaptive_enabled: bool = False
    book_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid")


class CreateCourseCapabilityOutput(ActionStatusMixin):
    """Output payload for course creation capability."""

    course_id: uuid.UUID | None = None
    title: str | None = None


class AppendCourseLessonCapabilityInput(CamelModel):
    """Input payload for course lesson append capability."""

    course_id: uuid.UUID
    lesson_title: str = Field(min_length=1)
    lesson_description: str | None = None
    module_name: str | None = None
    generate_content: bool = True
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid")


class AppendCourseLessonCapabilityOutput(ActionStatusMixin):
    """Output payload for course lesson append capability."""

    course_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    content_generated: bool = False


class ExtendLessonWithContextCapabilityInput(CamelModel):
    """Input payload for lesson extension capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    context: str = Field(min_length=1)
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid")


class RegenerateLessonWithContextCapabilityInput(CamelModel):
    """Input payload for lesson regeneration capability."""

    course_id: uuid.UUID
    lesson_id: uuid.UUID
    context: str = Field(min_length=1)
    confirmed: bool = False

    model_config = ConfigDict(extra="forbid")


class LessonMutationCapabilityOutput(ActionStatusMixin):
    """Output payload for lesson extend/regenerate capabilities."""

    course_id: uuid.UUID | None = None
    lesson_id: uuid.UUID | None = None
    lesson_title: str | None = None
    has_content: bool = False
