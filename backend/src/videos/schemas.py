import json
import uuid
from datetime import datetime
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from pydantic import ConfigDict, Field, JsonValue, field_validator

from src.config.schema_casing import CamelModel


VideoRagStatus = Literal["pending", "processing", "completed", "failed"]
VideoLearningStatus = Literal["not_started", "in_progress", "completed"]


class VideoBase(CamelModel):
    """Base schema for video data."""

    model_config = ConfigDict(str_strip_whitespace=True)

    youtube_id: str = Field(min_length=1, max_length=20)
    url: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=500)
    channel: str = Field(min_length=1, max_length=255)
    channel_id: str = Field(min_length=1, max_length=50)
    duration: int = Field(ge=0, description="Duration in seconds (0 for live/unknown)")
    thumbnail_url: str | None = Field(None, max_length=500)
    description: str | None = None
    tags: list[str] | None = Field(default_factory=list)
    published_at: datetime | None = None


class VideoCreate(CamelModel):
    """Schema for creating a new video."""

    url: str = Field(description="YouTube video URL")

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the URL is a valid YouTube URL."""
        try:
            parsed_url = urlparse(v.strip())
        except ValueError:
            msg = "Invalid YouTube URL"
            raise ValueError(msg) from None

        hostname = (parsed_url.hostname or "").lower()
        path_segments = [segment for segment in parsed_url.path.split("/") if segment]

        is_short = hostname in {"youtu.be", "www.youtu.be"} and bool(path_segments)
        is_watch = (hostname == "youtube.com" or hostname.endswith(".youtube.com")) and (
            (parsed_url.path == "/watch" and bool(parse_qs(parsed_url.query).get("v", [""])[0]))
            or (len(path_segments) >= 2 and path_segments[0] in {"embed", "v", "shorts", "live"})
        )

        if not is_short and not is_watch:
            msg = "Invalid YouTube URL"
            raise ValueError(msg)
        return v


class VideoUpdate(CamelModel):
    """Schema for updating video data."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    tags: list[str] | None = None


class VideoInDB(VideoBase):
    """Schema for video stored in database."""

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator("tags", mode="before")
    @classmethod
    def parse_tags_json(cls, v: str | list[str] | None) -> list[str]:
        """Parse tags from JSON string if needed."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except (json.JSONDecodeError, TypeError):
                return []
        return v or []

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        """Override to handle tags serialization."""
        data = super().model_dump(**kwargs)
        # Parse tags from JSON string if stored as text
        if isinstance(data.get("tags"), str):
            try:
                data["tags"] = json.loads(data["tags"])
            except (json.JSONDecodeError, TypeError):
                data["tags"] = []
        return data


class VideoResponse(VideoInDB):
    """Schema for video API response."""

    already_exists: bool = Field(default=False, description="True if video already existed in library")


class VideoListResponse(CamelModel):
    """Schema for paginated video list response."""

    items: list[VideoResponse]
    total: int
    page: int
    pages: int


class VideoChapterBase(CamelModel):
    """Base schema for video chapter."""

    chapter_number: int = Field(ge=1)
    title: str = Field(max_length=500)
    start_time: int | None = Field(None, ge=0, description="Start time in seconds")
    end_time: int | None = Field(None, ge=0, description="End time in seconds")
    status: VideoLearningStatus = "not_started"


class VideoChapterResponse(VideoChapterBase):
    """Schema for video chapter response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class VideoChapterStatusUpdate(CamelModel):
    """Schema for updating video chapter status."""

    status: VideoLearningStatus


class VideoChapterProgressSync(CamelModel):
    """Schema for syncing chapter progress from web app."""

    completed_chapter_ids: list[uuid.UUID] = Field(description="List of completed chapter IDs")
    total_chapters: int = Field(gt=0, description="Total number of chapters")


class TranscriptSegment(CamelModel):
    """Schema for video transcript segment with timestamp."""

    start_time: float = Field(ge=0, description="Start time in seconds")
    end_time: float = Field(ge=0, description="End time in seconds")
    text: str = Field(description="Transcript text for this segment")


class VideoTranscriptResponse(CamelModel):
    """Schema for video transcript response."""

    video_id: uuid.UUID
    segments: list[TranscriptSegment] = Field(description="List of transcript segments")
    total_segments: int


class VideoDetailsResponse(VideoResponse):
    """Video details response with chapters, transcript status, and progress."""

    chapters: list[VideoChapterResponse]
    transcript_info: dict[str, JsonValue] | None = None
    progress: dict[str, JsonValue]


class RAGStatusResponse(CamelModel):
    """Response model for RAG embedding status."""

    model_config = ConfigDict(from_attributes=True)

    video_id: uuid.UUID
    rag_status: VideoRagStatus
    rag_processed_at: str | None = None
    message: str
