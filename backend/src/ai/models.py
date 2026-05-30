"""Pydantic models for AI-related data structures."""

import json
import re
from typing import Literal, cast

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationInfo, field_validator, model_validator


def _normalize_slug_text(value: object) -> str:
    text = str(value or "").strip().lower()
    slug_chars: list[str] = []
    last_was_separator = False
    for char in text:
        if char.isalnum():
            slug_chars.append(char)
            last_was_separator = False
            continue
        if slug_chars and not last_was_separator:
            slug_chars.append("-")
        last_was_separator = True
    return "".join(slug_chars).strip("-")


def _coerce_slug(value: object, *, field: str) -> str:
    text = _normalize_slug_text(value)
    if not text:
        msg = f"{field} must not be empty"
        raise ValueError(msg)
    return text


def _coerce_slug_list(values: object, *, field: str) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        msg = f"{field} must be provided as a list of slugs"
        raise ValueError(msg)  # noqa: TRY004 - used by Pydantic validators for schema errors.
    return [_coerce_slug(item, field=field) for item in values if str(item or "").strip()]


def _float_input(value: object) -> str | int | float:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        msg = "Value must be numeric"
        raise TypeError(msg)
    return value


class PlanAction(BaseModel):
    """Action describing either a command or a code patch."""

    type: Literal["command", "patch"] = Field(description="Action type")
    command: str | None = Field(default=None, description="Shell command to execute")
    user: Literal["user", "root"] | None = Field(
        default=None,
        description="Sandbox user to execute command as",
    )
    path: str | None = Field(default=None, description="File path for patch application")
    language: str | None = Field(default=None, description="Code language for patch context")
    original: str | None = Field(default=None, description="Original snippet to replace")
    replacement: str | None = Field(default=None, description="Replacement snippet")
    explanation: str | None = Field(default=None, description="Brief explanation of the change")

    model_config = ConfigDict(extra="forbid")

    @field_validator("command")
    @classmethod
    def _require_command(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("type") != "command":
            return value
        if not value or not value.strip():
            msg = "Command action requires non-empty command"
            raise ValueError(msg)
        return value.strip()

    @field_validator("replacement")
    @classmethod
    def _validate_replacement_length(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("type") != "patch":
            return value
        if not value or not value.strip():
            msg = "Patch action requires replacement text"
            raise ValueError(msg)
        line_count = value.count("\n") + 1
        if line_count > 100:
            msg = "Patch replacement must be ≤ 100 lines"
            raise ValueError(msg)
        return value

    @field_validator("path", "original")
    @classmethod
    def _require_patch_fields(cls, value: str | None, info: ValidationInfo) -> str | None:
        if info.data.get("type") != "patch":
            return value
        if not value or not value.strip():
            field_name = info.field_name
            msg = f"Patch action requires field '{field_name}'"
            raise ValueError(msg)
        return value

    @field_validator("user")
    @classmethod
    def _default_user(cls, value: str | None, info: ValidationInfo) -> str:
        if info.data.get("type") == "command":
            return value or "user"
        return "user"


class Lesson(BaseModel):
    """Model for a lesson in the course structure."""

    title: str = Field(description="Title of the lesson", max_length=255)
    description: str = Field(description="Brief description of what the lesson covers")
    module: str | None = Field(
        default=None,
        description="Optional module/section name for grouping",
        max_length=255,
    )
    slug: str | None = Field(default=None, description="Optional lesson slug reference")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("title", "description", "module", mode="before")
    @classmethod
    def _normalize_text(cls, value: object, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if info.field_name in {"title", "description"} and not text:
            msg = f"{info.field_name} must not be empty"
            raise ValueError(msg)
        return text or None

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug_field(cls, value: object) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _coerce_slug(value, field="Lesson slug")


class CourseOutlineInfo(BaseModel):
    """Top-level metadata about a generated course."""

    slug: str | None = None
    title: str = Field(max_length=200)
    description: str | None = None
    setup_commands: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Course title must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("setup_commands", mode="before")
    @classmethod
    def _ensure_setup_commands(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []


class CourseStructure(BaseModel):
    """Model for the course structure returned by AI."""

    course: CourseOutlineInfo
    lessons: list[Lesson]

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @model_validator(mode="before")
    @classmethod
    def _coerce_legacy_shape(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = cast("dict[str, object]", data)
        if "course" in payload:
            return payload
        # Legacy shape: title/description/setup_commands at root level
        return {
            "course": {
                "title": payload.get("title"),
                "description": payload.get("description"),
                "setup_commands": payload.get("setup_commands", []),
                "slug": payload.get("slug"),
            },
            "lessons": payload.get("lessons", []),
        }


class AdaptiveCourseMeta(BaseModel):
    """Minimal course metadata emitted by adaptive course planning."""

    slug: str | None = None
    title: str = Field(max_length=200)
    description: str | None = None
    setup_commands: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def _coerce_index(value: object, *, field: str) -> int:
    try:
        idx = int(float(_float_input(value)))
    except (TypeError, ValueError) as exc:
        msg = f"{field} must be an integer"
        raise ValueError(msg) from exc
    if idx < 0:
        msg = f"{field} must be >= 0"
        raise ValueError(msg)
    return idx


class AdaptiveLessonPlan(BaseModel):
    """Lesson planning payload aligned with adaptive concept assignments."""

    index: int
    title: str | None = Field(default=None, max_length=255)
    description: str = Field(min_length=1)
    module: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(extra="forbid")

    @field_validator("index", mode="before")
    @classmethod
    def _normalize_index(cls, value: object) -> int:
        return _coerce_index(value, field="Lesson index")

    @field_validator("title", "module", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("description", mode="before")
    @classmethod
    def _strip_required_description(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Lesson description must not be empty"
            raise ValueError(msg)
        return text


class AdaptiveConceptNode(BaseModel):
    """Single concept node returned by adaptive course planning."""

    title: str = Field(max_length=255)
    initial_mastery: float | None = Field(default=None, alias="initialMastery")
    slug: str | None = Field(default=None, max_length=200)

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Concept title must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("initial_mastery", mode="before")
    @classmethod
    def _coerce_initial_mastery(cls, value: object) -> float | None:
        if value is None or value == "":
            return None
        try:
            mastery = float(_float_input(value))
        except (TypeError, ValueError) as exc:
            msg = "initialMastery must be a float between 0.0 and 1.0"
            raise ValueError(msg) from exc
        if not 0.0 <= mastery <= 1.0:
            msg = "initialMastery must be between 0.0 and 1.0"
            raise ValueError(msg)
        return mastery

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: object) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _coerce_slug(value, field="Adaptive concept slug")


class AdaptiveConfusor(BaseModel):
    """Confusable concept emitted for adaptive planning (index-keyed)."""

    index: int
    risk: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("index", mode="before")
    @classmethod
    def _normalize_index(cls, value: object) -> int:
        return _coerce_index(value, field="Confusor index")

    @field_validator("risk", mode="before")
    @classmethod
    def _coerce_risk(cls, value: object) -> float:
        try:
            risk = float(_float_input(value))
        except (TypeError, ValueError) as exc:
            msg = "Risk must be a float between 0.0 and 1.0"
            raise ValueError(msg) from exc
        if not 0.0 <= risk <= 1.0:
            msg = "Risk must be between 0.0 and 1.0"
            raise ValueError(msg)
        return risk


class AdaptiveConfusorSet(BaseModel):
    """Confusor mapping for a base concept index."""

    index: int
    confusors: list[AdaptiveConfusor] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("index", mode="before")
    @classmethod
    def _normalize_index(cls, value: object) -> int:
        return _coerce_index(value, field="Confusor set index")


class AdaptiveConceptEdge(BaseModel):
    """Directed prerequisite edge expressed with camelCase fields (index-keyed)."""

    source_index: int = Field(alias="sourceIndex")
    prereq_index: int = Field(alias="prereqIndex")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("source_index", mode="before")
    @classmethod
    def _normalize_source(cls, value: object) -> int:
        return _coerce_index(value, field="sourceIndex")

    @field_validator("prereq_index", mode="before")
    @classmethod
    def _normalize_prereq(cls, value: object) -> int:
        return _coerce_index(value, field="prereqIndex")


class ConfusorCandidate(BaseModel):
    """Potential confusion pair emitted for adaptive planning."""

    a: str
    b: str
    note: str

    model_config = ConfigDict(extra="forbid")


class AdaptiveConceptGraph(BaseModel):
    """Aggregate concept graph payload used to seed ConceptFlow."""

    nodes: list[AdaptiveConceptNode]
    edges: list[AdaptiveConceptEdge] = Field(default_factory=list)
    layers: list[list[int]] = Field(default_factory=list)
    confusors: list[AdaptiveConfusorSet] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("layers", mode="before")
    @classmethod
    def _normalize_layers(cls, value: object) -> list[list[int]]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[list[int]] = []
        for raw_layer in value:
            if not isinstance(raw_layer, list):
                continue
            layer: list[int] = []
            for item in raw_layer:
                if item is None or str(item).strip() == "":
                    continue
                try:
                    layer.append(_coerce_index(item, field="Layer index"))
                except ValueError:
                    continue
            normalized.append(layer)
        return normalized


class AdaptiveOutlineMeta(BaseModel):
    """Outline metadata required for adaptive courses."""

    scope: str
    concept_graph: AdaptiveConceptGraph = Field(alias="conceptGraph")

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class AdaptiveCourseStructure(BaseModel):
    """Full adaptive course generation payload."""

    course: AdaptiveCourseMeta
    ai_outline_meta: AdaptiveOutlineMeta
    lessons: list[AdaptiveLessonPlan] = Field(default_factory=list)

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    def layer_index(self) -> dict[int, int]:
        """Map node indices to their layer index for difficulty heuristics."""
        lookup: dict[int, int] = {}
        for layer_idx, layer in enumerate(self.ai_outline_meta.concept_graph.layers):
            for node_idx in layer:
                if node_idx not in lookup:
                    lookup[node_idx] = layer_idx
        return lookup


class ConceptNode(BaseModel):
    """Single concept node in an adaptive graph."""

    name: str
    description: str
    initial_mastery: float = Field(default=0.0, ge=0.0, le=1.0)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    slug: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("name", "description", mode="before")
    @classmethod
    def _strip_text(cls, value: object) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Concept text must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("difficulty", mode="before")
    @classmethod
    def _normalize_difficulty(cls, value: object) -> int | None:
        if value is None or value == "":
            return None
        try:
            difficulty = int(float(_float_input(value)))
        except (TypeError, ValueError) as exc:
            msg = "Difficulty must be an integer between 1 and 5"
            raise ValueError(msg) from exc
        if not 1 <= difficulty <= 5:
            msg = "Difficulty must be between 1 and 5"
            raise ValueError(msg)
        return difficulty

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: object) -> str | None:
        if value is None:
            return None
        text = str(value).strip().lower()
        return text or None


class ConceptEdge(BaseModel):
    """Directed edge between two concepts."""

    source_slug: str
    prereq_slug: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("source_slug", "prereq_slug", mode="before")
    @classmethod
    def _validate_endpoint(cls, value: object) -> str:
        text = str(value or "").strip().lower()
        if not text:
            msg = "Edge endpoint must not be empty"
            raise ValueError(msg)
        return text


class ConceptConfusor(BaseModel):
    """Confusable concept link with associated risk."""

    slug: str
    risk: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: object) -> str:
        return _coerce_slug(value, field="Confusor slug")

    @field_validator("risk", mode="before")
    @classmethod
    def _coerce_risk(cls, value: object) -> float:
        try:
            risk = float(_float_input(value))
        except (TypeError, ValueError) as exc:
            msg = "Risk must be a float between 0.0 and 1.0"
            raise ValueError(msg) from exc
        if not 0.0 <= risk <= 1.0:
            msg = "Risk must be between 0.0 and 1.0"
            raise ValueError(msg)
        return risk


class ConceptConfusorSet(BaseModel):
    """Set of confusable concepts for a given node."""

    slug: str
    confusable_with: list[ConceptConfusor] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: object) -> str:
        return _coerce_slug(value, field="Confusor set slug")


class ConceptGraph(BaseModel):
    """Structured concept graph returned by the LLM."""

    nodes: list[ConceptNode]
    edges: list[ConceptEdge] = Field(default_factory=list)
    confusors: list[ConceptConfusorSet] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("nodes")
    @classmethod
    def _require_nodes(cls, value: list[ConceptNode]) -> list[ConceptNode]:
        if not value:
            msg = "At least one concept node is required"
            raise ValueError(msg)
        return value


class SelfAssessmentQuestion(BaseModel):
    """Single-select self-assessment question."""

    type: Literal["single_select"] = Field(description="Question presentation type")
    question: str = Field(description="Learner-facing question text")
    options: list[str] = Field(description="Selectable options")

    model_config = ConfigDict(extra="forbid")

    @field_validator("question")
    @classmethod
    def _validate_question(cls, value: str) -> str:
        text = value.strip()
        if not text:
            msg = "Question must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("options", mode="before")
    @classmethod
    def _normalize_options(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(option).strip() for option in value if str(option).strip()]
        return [str(value).strip()]

    @field_validator("options")
    @classmethod
    def _validate_options(cls, value: list[str]) -> list[str]:
        if len(value) < 3 or len(value) > 5:
            msg = "Options must contain between 3 and 5 entries"
            raise ValueError(msg)
        return value


class SelfAssessmentQuiz(BaseModel):
    """Structured payload for self-assessment questions."""

    questions: list[SelfAssessmentQuestion] = Field(description="Collection of self-assessment questions")

    model_config = ConfigDict(extra="forbid")

    @field_validator("questions", mode="before")
    @classmethod
    def _normalize_questions(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, list):
            return list(value)
        return [value]

    @field_validator("questions")
    @classmethod
    def _validate_questions(cls, value: list[SelfAssessmentQuestion]) -> list[SelfAssessmentQuestion]:
        filtered = [question for question in value if question.options]
        if not filtered:
            msg = "At least one question is required"
            raise ValueError(msg)
        if len(filtered) > 10:
            return filtered[:10]
        return filtered


SupportedInlineComponent = Literal["LatexExpression", "FreeForm", "JXGBoard"]
InlineGradeKind = Literal["latex_expression", "jxg_state", "practice_answer"]

_PLACEHOLDER_PATTERN = re.compile(r"^__Q[A-Za-z0-9_]+__$")
_QUESTION_ID_REFERENCE = re.compile(r'questionId\s*=\s*"(__Q[A-Za-z0-9_]+__)"')
_FORBIDDEN_CONTENT_ATTRS = (
    "expectedAnswer=",
    "expectedLatex=",
    "expectedState=",
    "sampleAnswer=",
    "solutionLatex=",
    "tolerance=",
    "perCheckTolerance=",
)


class GeneratedInlineQuestion(BaseModel):
    """One inline practice question generated alongside lesson content.

    The lesson body references this question via a ``questionId="<placeholder>"`` attribute
    on a supported MDX component. The server materializes the question into a
    ``LearningQuestion`` row and rewrites the placeholder to the row's UUID before sending
    the lesson to the client. Answer data never leaves the server.
    """

    placeholder: str = Field(description='Placeholder used in content, e.g. "__Q0__"')
    component: SupportedInlineComponent = Field(description="MDX component name used in content")
    question: str = Field(description="Question prompt text")
    hints: list[str] = Field(default_factory=list, description="Ordered hint strings")
    practice_context: str = Field(default="inline", description="Practice context label")
    grade_kind: InlineGradeKind = Field(description="Grading strategy applied to attempts")
    answer_kind: str | None = Field(default=None, description='Answer format, e.g. "text" or "latex"')
    expected_answer: str | None = Field(default=None, description="Expected text answer (latex or plain)")
    expected_payload: dict[str, JsonValue] = Field(
        default_factory=dict,
        description="Structured expected data for graders (e.g. expectedLatex, expectedState, criteria)",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_per_component(self) -> "GeneratedInlineQuestion":
        if not _PLACEHOLDER_PATTERN.match(self.placeholder):
            msg = f'placeholder must match "__Q<id>__", got {self.placeholder!r}'
            raise ValueError(msg)
        if self.component == "LatexExpression":
            if self.grade_kind != "latex_expression":
                msg = "LatexExpression requires grade_kind='latex_expression'"
                raise ValueError(msg)
            if not self.expected_answer or self.answer_kind != "latex":
                msg = "LatexExpression requires expected_answer (latex) and answer_kind='latex'"
                raise ValueError(msg)
        elif self.component == "JXGBoard":
            if self.grade_kind != "jxg_state":
                msg = "JXGBoard requires grade_kind='jxg_state'"
                raise ValueError(msg)
            if not self.expected_payload.get("expectedState"):
                msg = "JXGBoard requires expected_payload['expectedState']"
                raise ValueError(msg)
        elif self.component == "FreeForm":
            if self.grade_kind != "practice_answer":
                msg = "FreeForm requires grade_kind='practice_answer'"
                raise ValueError(msg)
            if not self.expected_answer:
                msg = "FreeForm requires expected_answer"
                raise ValueError(msg)
        return self


class GeneratedLesson(BaseModel):
    """Lesson body plus inline practice questions returned by the LLM.

    ``content`` is Markdown/MDX. Supported inline practice components reference a question
    via ``questionId="__Q<id>__"`` placeholders. Each placeholder must have a matching
    ``GeneratedInlineQuestion`` in ``inline_questions``. Forbidden answer attributes are
    rejected to prevent leaking grading data to the client.
    """

    content: str = Field(description="Lesson body in Markdown/MDX with questionId placeholders")
    inline_questions: list[GeneratedInlineQuestion] = Field(
        default_factory=list,
        description="Server-owned practice questions referenced by placeholder in content",
    )

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _validate_placeholders_consistent(self) -> "GeneratedLesson":
        declared = [question.placeholder for question in self.inline_questions]
        if len(set(declared)) != len(declared):
            msg = "inline_questions placeholders must be unique"
            raise ValueError(msg)
        referenced = set(_QUESTION_ID_REFERENCE.findall(self.content))
        declared_set = set(declared)
        missing = sorted(referenced - declared_set)
        if missing:
            msg = f"content references placeholders not declared in inline_questions: {missing}"
            raise ValueError(msg)
        orphaned = sorted(declared_set - referenced)
        if orphaned:
            msg = f"inline_questions declared but not referenced in content: {orphaned}"
            raise ValueError(msg)
        for forbidden in _FORBIDDEN_CONTENT_ATTRS:
            if forbidden in self.content:
                msg = f"lesson content must not contain {forbidden!r}; place it in inline_questions"
                raise ValueError(msg)
        return self


class ExecutionFile(BaseModel):
    """File that should be created inside the sandbox before execution."""

    path: str = Field(description="Absolute or relative filesystem path inside the sandbox")
    content: str = Field(description="File contents to write")
    executable: bool = Field(default=False, description="Whether to mark the file as executable")

    model_config = ConfigDict(extra="forbid")


class ExecutionPlan(BaseModel):
    """Structured plan generated by the LLM for sandbox execution."""

    language: str = Field(description="Normalized language identifier (informational)")
    summary: str = Field(description="High-level summary of the plan")
    files: list[ExecutionFile] = Field(default_factory=list, description="Files to materialize inside the sandbox")
    actions: list[PlanAction] = Field(default_factory=list, description="Ordered execution/patch actions")
    setup_commands: list[str] = Field(
        default_factory=list,
        description="Idempotent setup commands (mkdir, chmod, etc.)",
    )
    install_commands: list[str] = Field(
        default_factory=list,
        description="Commands that install system or language packages",
    )
    run_commands: list[str] = Field(
        default_factory=list,
        description="Commands that should be executed to run the user code",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Environment variables to set for subsequent commands",
    )

    model_config = ConfigDict(extra="forbid")

    @staticmethod
    def _decode_json_blob(value: object) -> object:
        if isinstance(value, str):
            candidate = value.strip()
            if candidate.startswith(("{", "[")):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return value
        return value

    @classmethod
    def _normalize_sequence_input(cls, value: object) -> list[object]:
        if value is None:
            return []
        if isinstance(value, list):
            normalized: list[object] = []
            for entry in value:
                decoded = cls._decode_json_blob(entry)
                if isinstance(decoded, list):
                    normalized.extend(decoded)
                else:
                    normalized.append(decoded)
            return normalized
        if isinstance(value, str):
            decoded = cls._decode_json_blob(value)
            if isinstance(decoded, list):
                return list(decoded)
            return [decoded]
        return [value]

    @field_validator("setup_commands", "install_commands", "run_commands", mode="before")
    @classmethod
    def _ensure_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @field_validator("files", mode="before")
    @classmethod
    def _normalize_files(cls, value: object) -> list[object]:
        normalized = cls._normalize_sequence_input(value)
        files: list[object] = []
        for entry in normalized:
            if isinstance(entry, dict):
                files.append(entry)
                continue
            if isinstance(entry, str):
                stripped = entry.strip()
                if stripped:
                    files.append({"path": stripped, "content": "", "executable": False})
                continue
            if entry is not None:
                files.append(entry)
        return files

    @field_validator("summary", "language")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("setup_commands", "install_commands", "run_commands")
    @classmethod
    def _validate_command_tokens(cls, commands: list[str]) -> list[str]:
        disallowed = {"sudo"}
        sanitized: list[str] = []
        for cmd in commands:
            lower = cmd.lower()
            if any(token in lower.split() for token in disallowed):
                msg = f"Command contains disallowed token: {cmd}"
                raise ValueError(msg)
            sanitized.append(cmd.strip())
        return sanitized

    @field_validator("actions", mode="before")
    @classmethod
    def _normalize_actions(cls, value: object) -> list[object]:
        normalized = cls._normalize_sequence_input(value)
        actions: list[object] = []
        for entry in normalized:
            if isinstance(entry, dict):
                actions.append(entry)
                continue
            if isinstance(entry, str):
                stripped = entry.strip()
                if stripped:
                    actions.append({"type": "command", "command": stripped, "user": "user"})
                continue
            if entry is not None:
                actions.append(entry)
        return actions
