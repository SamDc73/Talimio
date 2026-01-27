"""Pydantic models for AI-related data structures."""

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


def _normalize_slug_text(value: Any) -> str:
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


def _coerce_slug(value: Any, *, field: str) -> str:
    text = _normalize_slug_text(value)
    if not text:
        msg = f"{field} must not be empty"
        raise ValueError(msg)
    return text


def _coerce_slug_list(values: Any, *, field: str) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        values = [values]
    if not isinstance(values, list):
        msg = f"{field} must be provided as a list of slugs"
        raise TypeError(msg)
    return [_coerce_slug(item, field=field) for item in values if str(item or "").strip()]


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

    title: str = Field(description="Title of the lesson")
    description: str = Field(description="Brief description of what the lesson covers")
    module: str | None = Field(
        default=None,
        description="Optional module/section name for grouping",
    )
    slug: str | None = Field(default=None, description="Optional lesson slug reference")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("title", "description", "module", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any, info: ValidationInfo) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if info.field_name in {"title", "description"} and not text:
            msg = f"{info.field_name} must not be empty"
            raise ValueError(msg)
        return text or None

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug_field(cls, value: Any) -> str | None:
        if value is None or str(value).strip() == "":
            return None
        return _coerce_slug(value, field="Lesson slug")


class CourseOutlineInfo(BaseModel):
    """Top-level metadata about a generated course."""

    slug: str | None = None
    title: str
    description: str | None = None
    setup_commands: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Course title must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("setup_commands", mode="before")
    @classmethod
    def _ensure_setup_commands(cls, value: Any) -> list[str]:
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
    def _coerce_legacy_shape(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if "course" in data:
            return data
        # Legacy shape: title/description/setup_commands at root level
        return {
            "course": {
                "title": data.get("title"),
                "description": data.get("description"),
                "setup_commands": data.get("setup_commands", []),
                "slug": data.get("slug"),
            },
            "lessons": data.get("lessons", []),
        }


class AdaptiveCourseMeta(BaseModel):
    """Minimal course metadata emitted by adaptive course planning."""

    slug: str | None = None
    title: str
    setup_commands: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid")


def _coerce_index(value: Any, *, field: str) -> int:
    try:
        idx = int(float(value))
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
    title: str | None = None
    description: str | None = None
    module: str | None = None

    model_config = ConfigDict(extra="forbid")

    @field_validator("index", mode="before")
    @classmethod
    def _normalize_index(cls, value: Any) -> int:
        return _coerce_index(value, field="Lesson index")

    @field_validator("title", "description", "module", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class AdaptiveConceptNode(BaseModel):
    """Single concept node returned by adaptive course planning."""

    title: str
    initial_mastery: float | None = Field(default=None, alias="initialMastery")
    slug: str | None = None

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("title", mode="before")
    @classmethod
    def _normalize_title(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Concept title must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("initial_mastery", mode="before")
    @classmethod
    def _coerce_initial_mastery(cls, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            mastery = float(value)
        except (TypeError, ValueError) as exc:
            msg = "initialMastery must be a float between 0.0 and 1.0"
            raise ValueError(msg) from exc
        if not 0.0 <= mastery <= 1.0:
            msg = "initialMastery must be between 0.0 and 1.0"
            raise ValueError(msg)
        return mastery

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: Any) -> str | None:
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
    def _normalize_index(cls, value: Any) -> int:
        return _coerce_index(value, field="Confusor index")

    @field_validator("risk", mode="before")
    @classmethod
    def _coerce_risk(cls, value: Any) -> float:
        try:
            risk = float(value)
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
    def _normalize_index(cls, value: Any) -> int:
        return _coerce_index(value, field="Confusor set index")


class AdaptiveConceptEdge(BaseModel):
    """Directed prerequisite edge expressed with camelCase fields (index-keyed)."""

    source_index: int = Field(alias="sourceIndex")
    prereq_index: int = Field(alias="prereqIndex")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    @field_validator("source_index", mode="before")
    @classmethod
    def _normalize_source(cls, value: Any) -> int:
        return _coerce_index(value, field="sourceIndex")

    @field_validator("prereq_index", mode="before")
    @classmethod
    def _normalize_prereq(cls, value: Any) -> int:
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
    def _normalize_layers(cls, value: Any) -> list[list[int]]:
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
    concept_tags: list[list[str]] = Field(default_factory=list, alias="conceptTags")

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @field_validator("concept_tags", mode="before")
    @classmethod
    def _normalize_concept_tags(cls, value: Any) -> list[list[str]]:
        if value is None:
            return []
        if not isinstance(value, list):
            return []
        normalized: list[list[str]] = []
        for raw in value:
            if isinstance(raw, list):
                normalized.append([str(entry).strip() for entry in raw if str(entry).strip()])
            elif isinstance(raw, str):
                stripped = raw.strip()
                normalized.append([stripped] if stripped else [])
            else:
                normalized.append([])
        return normalized


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

    def concept_tags_for_index(self, index: int) -> list[str]:
        """Return the tag list for a node index, if any."""
        if index < 0:
            return []
        tags = self.ai_outline_meta.concept_tags
        if index >= len(tags):
            return []
        return tags[index]


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
    def _strip_text(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            msg = "Concept text must not be empty"
            raise ValueError(msg)
        return text

    @field_validator("difficulty", mode="before")
    @classmethod
    def _normalize_difficulty(cls, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            difficulty = int(float(value))
        except (TypeError, ValueError) as exc:
            msg = "Difficulty must be an integer between 1 and 5"
            raise ValueError(msg) from exc
        if not 1 <= difficulty <= 5:
            msg = "Difficulty must be between 1 and 5"
            raise ValueError(msg)
        return difficulty

    @field_validator("slug", mode="before")
    @classmethod
    def _normalize_slug(cls, value: Any) -> str | None:
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
    def _validate_endpoint(cls, value: Any) -> str:
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
    def _normalize_slug(cls, value: Any) -> str:
        return _coerce_slug(value, field="Confusor slug")

    @field_validator("risk", mode="before")
    @classmethod
    def _coerce_risk(cls, value: Any) -> float:
        try:
            risk = float(value)
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
    def _normalize_slug(cls, value: Any) -> str:
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
    def _normalize_options(cls, value: Any) -> list[str]:
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
    def _normalize_questions(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
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


class LessonContent(BaseModel):
    """Model for lesson content returned by AI."""

    body: str = Field(description="The full lesson content in Markdown format")

    model_config = ConfigDict(extra="forbid")


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
    def _decode_json_blob(value: Any) -> Any:
        if isinstance(value, str):
            candidate = value.strip()
            if candidate.startswith(("{", "[")):
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    return value
        return value

    @classmethod
    def _normalize_sequence_input(cls, value: Any) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, list):
            normalized: list[Any] = []
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
                return decoded
            return [decoded]
        return [value]

    @field_validator("setup_commands", "install_commands", "run_commands", mode="before")
    @classmethod
    def _ensure_list(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str) and value.strip():
            return [value.strip()]
        return []

    @field_validator("files", mode="before")
    @classmethod
    def _normalize_files(cls, value: Any) -> list[Any]:
        normalized = cls._normalize_sequence_input(value)
        files: list[Any] = []
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
    def _normalize_actions(cls, value: Any) -> list[Any]:
        normalized = cls._normalize_sequence_input(value)
        actions: list[Any] = []
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
