"""Highlight payload validation.

Each content type validates against the schema that matches its data shape:

- ``video``  -> strict transcript timing (``VideoHighlightData``)
- ``lesson`` -> plain selected text plus optional location (``GenericHighlightData``)
- ``book``   -> PDF position, EPUB CFI, or generic text, detected from the payload
"""

from pydantic import ConfigDict, Field, JsonValue, ValidationInfo, field_validator

from src.config.schema_casing import CamelModel


class PDFHighlightData(CamelModel):
    """Validation schema for PDF highlight data."""

    # Required fields for PDF highlights
    text: str = Field(min_length=1, max_length=10000, description="Selected text content")
    page: int = Field(ge=1, description="Page number (1-based)")

    # Position data for PDF highlighting
    position: dict[str, object] = Field(description="Position data for PDF highlight")

    # Optional fields
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: object) -> dict[str, object]:
        """Validate PDF position data structure."""
        if not isinstance(v, dict):
            msg = "Position must be a dictionary"
            raise ValueError(msg)  # ruff: ignore[type-check-without-type-error] - Pydantic validators should report schema errors as ValueError.
        position = {key: value for key, value in v.items() if isinstance(key, str)}

        # Required position fields for PDF
        required_fields = {"rects", "pageNumber"}
        if not all(field in position for field in required_fields):
            msg = f"Position must contain fields: {required_fields}"
            raise ValueError(msg)

        # Validate rects array
        rects = position.get("rects", [])
        if not isinstance(rects, list) or not rects:
            msg = "Position rects must be a non-empty array"
            raise ValueError(msg)

        # Validate each rect
        for i, rect in enumerate(rects):
            if not isinstance(rect, dict):
                msg = f"Rect {i} must be a dictionary"
                raise ValueError(msg)  # ruff: ignore[type-check-without-type-error] - Pydantic validators should report schema errors as ValueError.

            rect_data = {key: value for key, value in rect.items() if isinstance(key, str)}
            rect_fields = {"x1", "y1", "x2", "y2", "width", "height"}
            if not all(field in rect_data for field in rect_fields):
                msg = f"Rect {i} must contain fields: {rect_fields}"
                raise ValueError(msg)

            # Validate numeric values
            for field in rect_fields:
                rect_value = rect_data.get(field)
                if not isinstance(rect_value, (int, float)) or rect_value < 0:
                    msg = f"Rect {i}.{field} must be a non-negative number"
                    raise ValueError(msg)

        # Validate page number consistency
        page_num = position.get("pageNumber")
        if not isinstance(page_num, int) or page_num < 1:
            msg = "Position pageNumber must be a positive integer"
            raise ValueError(msg)

        return position


class VideoHighlightData(CamelModel):
    """Validation schema for video highlight data."""

    # Required fields for video highlights
    text: str = Field(min_length=1, max_length=10000, description="Selected text from transcript")
    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")

    # Optional fields
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    # Video-specific optional fields
    transcript_index: int | None = Field(None, ge=0, description="Index in transcript array")
    speaker: str | None = Field(None, max_length=100, description="Speaker name if available")

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: float, info: ValidationInfo) -> float:
        """Ensure end_time is after start_time."""
        start_time = info.data.get("start_time")
        if isinstance(start_time, (int, float)) and v <= start_time:
            msg = "end_time must be greater than start_time"
            raise ValueError(msg)
        return v


class EPUBHighlightData(CamelModel):
    """Validation schema for EPUB highlight data."""

    # Required fields for EPUB highlights
    text: str = Field(min_length=1, max_length=10000, description="Selected text content")
    cfi: str = Field(min_length=1, description="Canonical Fragment Identifier")

    # Optional fields
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    # EPUB-specific optional fields
    chapter: str | None = Field(None, max_length=200, description="Chapter title or identifier")
    spine_index: int | None = Field(None, ge=0, description="Spine index in EPUB")

    @field_validator("cfi")
    @classmethod
    def validate_cfi(cls, v: str) -> str:
        """Validate EPUB CFI format."""
        if not v.startswith("epubcfi("):
            msg = "CFI must start with 'epubcfi('"
            raise ValueError(msg)
        if not v.endswith(")"):
            msg = "CFI must end with ')'"
            raise ValueError(msg)
        return v


class GenericHighlightData(CamelModel):
    """Validation schema for plain selected text plus optional location data."""

    # Minimal required field
    text: str = Field(min_length=1, max_length=10000, description="Selected text content")

    # Optional fields that any highlight type might have
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    model_config = ConfigDict(extra="allow")


def _book_schema(data: dict[str, JsonValue]) -> type[CamelModel]:
    """Pick the book schema from the payload shape: PDF position, EPUB CFI, else generic text."""
    position = data.get("position")
    if isinstance(position, dict) and "rects" in position and "pageNumber" in position:
        return PDFHighlightData
    if isinstance(data.get("cfi"), str):
        return EPUBHighlightData
    return GenericHighlightData


def validate_highlight_data(data: dict[str, JsonValue], content_type: str) -> dict[str, object]:
    """Validate a highlight payload for its content type and return the normalized blob.

    Raises ``pydantic.ValidationError`` when the payload does not match its schema.
    """
    if content_type == "video":
        schema_class: type[CamelModel] = VideoHighlightData
    elif content_type == "lesson":
        schema_class = GenericHighlightData
    else:
        schema_class = _book_schema(data)
    return schema_class.model_validate(data).model_dump(by_alias=True)
