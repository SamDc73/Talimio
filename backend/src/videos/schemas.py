import json
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VideoBase(BaseModel):
    """Base schema for video data."""

    youtube_id: str = Field(..., min_length=1, max_length=20)
    url: str = Field(..., min_length=1, max_length=255)
    title: str = Field(..., min_length=1, max_length=500)
    channel: str = Field(..., min_length=1, max_length=255)
    channel_id: str = Field(..., min_length=1, max_length=50)
    duration: int = Field(..., gt=0, description="Duration in seconds")
    thumbnail_url: str | None = Field(None, max_length=500)
    description: str | None = None
    tags: list[str] | None = Field(default_factory=list)
    published_at: datetime | None = None

    class Config:
        str_strip_whitespace = True


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

    title: str | None = Field(None, min_length=1, max_length=500)
    description: str | None = None
    tags: list[str] | None = None

    class Config:
        str_strip_whitespace = True


class VideoProgressUpdate(BaseModel):
    """Schema for updating video progress."""

    last_position: float = Field(..., ge=0, description="Current position in seconds")

    class Config:
        str_strip_whitespace = True


class VideoInDB(VideoBase):
    """Schema for video stored in database."""

    id: int
    last_position: float = 0.0
    completion_percentage: float = 0.0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    def model_dump(self, **kwargs):
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



class VideoListResponse(BaseModel):
    """Schema for paginated video list response."""

    items: list[VideoResponse]
    total: int
    page: int
    size: int
    pages: int
