import json
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoBase(BaseModel):
    """Base schema for video data."""

    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    youtube_id: str = Field(..., min_length=1, max_length=20, alias="youtubeId")
    url: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=500)
    channel: str = Field(..., min_length=1, max_length=255)
    channel_id: str = Field(..., min_length=1, max_length=50, alias="channelId")
    duration: int = Field(..., gt=0, description="Duration in seconds")
    thumbnail_url: str | None = Field(None, max_length=500, alias="thumbnailUrl")
    description: str | None = None
    tags: list[str] | None = Field(default_factory=list)
    transcript: str | None = None
    published_at: datetime | None = Field(None, alias="publishedAt")


class VideoCreate(BaseModel):
    """Schema for creating a new video."""

    url: str = Field(..., description="YouTube video URL")

    @field_validator("url")
    @classmethod
    def validate_youtube_url(cls, v: str) -> str:
        """Validate that the URL is a valid YouTube URL."""
        if not any(domain in v for domain in ["youtube.com/watch", "youtu.be/"]):
            msg = "Invalid YouTube URL"
            raise ValueError(msg)
        return v


class VideoUpdate(BaseModel):
    """Schema for updating video data."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    tags: list[str] | None = None


class VideoProgressUpdate(BaseModel):
    """Schema for updating video progress."""

    model_config = ConfigDict(str_strip_whitespace=True, populate_by_name=True)

    last_position: float = Field(..., ge=0, description="Current position in seconds", alias="lastPosition")


class VideoInDB(VideoBase):
    """Schema for video stored in database."""

    id: int
    uuid: UUID
    last_position: float = Field(0.0, alias="lastPosition")
    completion_percentage: float = Field(0.0, alias="completionPercentage")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

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


class VideoListResponse(BaseModel):
    """Schema for paginated video list response."""

    items: list[VideoResponse]
    total: int
    page: int
    pages: int


# Chapter schemas for Phase 2.3
class VideoChapterBase(BaseModel):
    """Base schema for video chapter."""

    model_config = ConfigDict(populate_by_name=True)

    chapter_number: int = Field(..., ge=1, alias="chapterNumber")
    title: str = Field(..., max_length=500)
    start_time: int | None = Field(None, ge=0, description="Start time in seconds", alias="startTime")
    end_time: int | None = Field(None, ge=0, description="End time in seconds", alias="endTime")
    status: str = Field(default="not_started", pattern="^(not_started|in_progress|done)$")


class VideoChapterResponse(VideoChapterBase):
    """Schema for video chapter response."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    video_uuid: UUID = Field(alias="videoUuid")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class VideoChapterStatusUpdate(BaseModel):
    """Schema for updating video chapter status."""

    status: str = Field(..., pattern="^(not_started|in_progress|done)$")


class VideoChapterProgressSync(BaseModel):
    """Schema for syncing chapter progress from web app."""

    completed_chapter_ids: list[str] = Field(
        ..., description="List of completed chapter IDs", alias="completedChapterIds"
    )
    total_chapters: int = Field(..., gt=0, description="Total number of chapters", alias="totalChapters")


class TranscriptSegment(BaseModel):
    """Schema for video transcript segment with timestamp."""

    model_config = ConfigDict(populate_by_name=True)

    start_time: float = Field(..., ge=0, description="Start time in seconds", alias="startTime")
    end_time: float = Field(..., ge=0, description="End time in seconds", alias="endTime")
    text: str = Field(..., description="Transcript text for this segment")


class VideoTranscriptResponse(BaseModel):
    """Schema for video transcript response."""

    model_config = ConfigDict(populate_by_name=True)

    video_uuid: str = Field(..., alias="videoUuid")
    segments: list[TranscriptSegment] = Field(..., description="List of transcript segments")
    total_segments: int = Field(..., alias="totalSegments")
