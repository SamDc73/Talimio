"""
Highlight Data Validation Schemas.

Provides comprehensive JSON schema validation for highlight data
to ensure data integrity across different content types (PDF, video, EPUB).
"""

import json
import logging
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator


logger = logging.getLogger(__name__)


class PDFHighlightData(BaseModel):
    """Validation schema for PDF highlight data."""

    # Required fields for PDF highlights
    text: str = Field(..., min_length=1, max_length=10000, description="Selected text content")
    page: int = Field(..., ge=1, description="Page number (1-based)")

    # Position data for PDF highlighting
    position: dict[str, Any] = Field(..., description="Position data for PDF highlight")

    # Optional fields
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    @field_validator("position")
    @classmethod
    def validate_position(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate PDF position data structure."""
        if not isinstance(v, dict):
            msg = "Position must be a dictionary"
            raise TypeError(msg)

        # Required position fields for PDF
        required_fields = {"rects", "pageNumber"}
        if not all(field in v for field in required_fields):
            msg = f"Position must contain fields: {required_fields}"
            raise ValueError(msg)

        # Validate rects array
        rects = v.get("rects", [])
        if not isinstance(rects, list) or not rects:
            msg = "Position rects must be a non-empty array"
            raise ValueError(msg)

        # Validate each rect
        for i, rect in enumerate(rects):
            if not isinstance(rect, dict):
                msg = f"Rect {i} must be a dictionary"
                raise TypeError(msg)

            rect_fields = {"x1", "y1", "x2", "y2", "width", "height"}
            if not all(field in rect for field in rect_fields):
                msg = f"Rect {i} must contain fields: {rect_fields}"
                raise ValueError(msg)

            # Validate numeric values
            for field in rect_fields:
                if not isinstance(rect[field], (int, float)) or rect[field] < 0:
                    msg = f"Rect {i}.{field} must be a non-negative number"
                    raise ValueError(msg)

        # Validate page number consistency
        page_num = v.get("pageNumber")
        if not isinstance(page_num, int) or page_num < 1:
            msg = "Position pageNumber must be a positive integer"
            raise ValueError(msg)

        return v


class VideoHighlightData(BaseModel):
    """Validation schema for video highlight data."""

    # Required fields for video highlights
    text: str = Field(..., min_length=1, max_length=10000, description="Selected text from transcript")
    start_time: float = Field(..., ge=0, description="Start time in seconds")
    end_time: float = Field(..., ge=0, description="End time in seconds")

    # Optional fields
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    # Video-specific optional fields
    transcript_index: int | None = Field(None, ge=0, description="Index in transcript array")
    speaker: str | None = Field(None, max_length=100, description="Speaker name if available")

    @field_validator("end_time")
    @classmethod
    def validate_time_range(cls, v: float, info: Any) -> float:
        """Ensure end_time is after start_time."""
        start_time = getattr(info, "data", {}).get("start_time")
        if start_time is not None and v <= start_time:
            msg = "end_time must be greater than start_time"
            raise ValueError(msg)
        return v


class EPUBHighlightData(BaseModel):
    """Validation schema for EPUB highlight data."""

    # Required fields for EPUB highlights
    text: str = Field(..., min_length=1, max_length=10000, description="Selected text content")
    cfi: str = Field(..., min_length=1, description="Canonical Fragment Identifier")

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


class GenericHighlightData(BaseModel):
    """Fallback validation schema for generic highlight data."""

    # Minimal required fields
    text: str = Field(..., min_length=1, max_length=10000, description="Selected text content")

    # Optional fields that any highlight type might have
    color: str | None = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$", description="Hex color code")
    note: str | None = Field(None, max_length=5000, description="User note/comment")

    # Allow any additional fields for extensibility
    class Config:
        """Permit arbitrary extra fields for flexibility."""

        extra = "allow"


def detect_highlight_type(data: dict[str, Any]) -> str:
    """
    Detect the type of highlight based on data structure.

    Args:
        data: Raw highlight data dictionary

    Returns
    -------
        Detected highlight type: 'pdf', 'video', 'epub', or 'generic'

    Note: This function detects the data structure type, not the content type.
    Content types ('book', 'course', 'video') are different from structure types.
    Books can contain PDF or EPUB data, courses can contain various structures.
    """
    # PDF highlights have position data with rects and pageNumber
    if "position" in data and isinstance(data["position"], dict):
        position = data["position"]
        if "rects" in position and "pageNumber" in position:
            return "pdf"

    # Video highlights have start_time and end_time
    if "start_time" in data and "end_time" in data:
        return "video"

    # EPUB highlights have CFI (Canonical Fragment Identifier)
    if "cfi" in data and isinstance(data["cfi"], str):
        return "epub"

    # Default to generic validation
    return "generic"


def validate_highlight_data(data: dict[str, Any], _content_type: str | None = None) -> dict[str, Any]:
    """
    Validate highlight data against appropriate schema.

    Args:
        data: Raw highlight data dictionary
        _content_type: Optional content type hint ('book', 'video', etc.)

    Returns
    -------
        Validated and normalized highlight data

    Raises
    ------
        ValidationError: If data doesn't match any valid schema
    """
    # Auto-detect type if not provided or if _content_type is too generic
    detected_type = detect_highlight_type(data)

    # Map content types to validation schemas
    schema_map = {
        "pdf": PDFHighlightData,
        "video": VideoHighlightData,
        "epub": EPUBHighlightData,
        "generic": GenericHighlightData,
    }

    # Prefer detected type over _content_type for validation
    schema_class = schema_map.get(detected_type, GenericHighlightData)

    try:
        # Validate using the appropriate schema
        validated_data = schema_class(**data)

        # Return as dictionary with type annotation
        result = validated_data.model_dump()
        result["_validation_type"] = detected_type

        logger.debug(f"Successfully validated {detected_type} highlight data")
        return result

    except ValidationError as e:
        logger.exception(f"Validation failed for {detected_type} highlight: {e}")

        # If strict validation fails, try generic schema as fallback
        if detected_type != "generic":
            try:
                logger.info("Attempting fallback to generic validation")
                validated_data = GenericHighlightData(**data)
                result = validated_data.model_dump()
                result["_validation_type"] = "generic"
                return result
            except ValidationError:
                pass

        # Re-raise the original validation error
        msg = f"Invalid highlight data: {e}"
        raise ValidationError(msg) from e


def validate_json_highlight_data(json_data: str | dict[str, Any], _content_type: str | None = None) -> dict[str, Any]:
    """
    Validate highlight data from JSON string or dictionary.

    Args:
        json_data: JSON string or dictionary containing highlight data
        _content_type: Optional content type hint

    Returns
    -------
        Validated highlight data dictionary

    Raises
    ------
        ValueError: If JSON is invalid
        ValidationError: If data doesn't match schema
    """
    # Parse JSON if needed
    if isinstance(json_data, str):
        try:
            data = json.loads(json_data)
        except json.JSONDecodeError as e:
            msg = f"Invalid JSON format: {e}"
            raise ValueError(msg) from e
    else:
        data = json_data

    if not isinstance(data, dict):
        msg = "Highlight data must be a JSON object"
        raise TypeError(msg)

    return validate_highlight_data(data, _content_type)


def get_validation_schema_for_type(highlight_type: str) -> type[BaseModel]:
    """
    Get the validation schema class for a specific highlight type.

    Args:
        highlight_type: Type of highlight ('pdf', 'video', 'epub', 'generic')

    Returns
    -------
        Pydantic model class for validation
    """
    schema_map = {
        "pdf": PDFHighlightData,
        "video": VideoHighlightData,
        "epub": EPUBHighlightData,
        "generic": GenericHighlightData,
    }

    return schema_map.get(highlight_type, GenericHighlightData)


def get_validation_examples() -> dict[str, dict[str, Any]]:
    """
    Get example valid highlight data for each type.

    Returns
    -------
        Dictionary mapping highlight types to example data
    """
    return {
        "pdf": {
            "text": "This is selected text from a PDF document.",
            "page": 1,
            "position": {
                "rects": [{"x1": 100.0, "y1": 200.0, "x2": 300.0, "y2": 220.0, "width": 200.0, "height": 20.0}],
                "pageNumber": 1,
            },
            "color": "#FFFF00",
            "note": "Important concept to remember",
        },
        "video": {
            "text": "This is text from the video transcript.",
            "start_time": 120.5,
            "end_time": 125.8,
            "color": "#FF6B6B",
            "note": "Key point discussed in the video",
            "transcript_index": 45,
            "speaker": "Dr. Smith",
        },
        "epub": {
            "text": "Selected text from an EPUB book.",
            "cfi": "epubcfi(/6/14[chapter01]!/4/2/8/2)",
            "color": "#4ECDC4",
            "note": "Interesting passage",
            "chapter": "Chapter 1: Introduction",
            "spine_index": 2,
        },
        "generic": {"text": "Generic selected text.", "color": "#95A5A6", "note": "General highlight"},
    }
