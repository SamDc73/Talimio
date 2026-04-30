import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel

from src.auth import CurrentAuth
from src.videos.facade import VideosFacade
from src.videos.schemas import (
    VideoChapterProgressSync,
    VideoChapterResponse,
    VideoChapterStatusUpdate,
    VideoCreate,
    VideoDetailsResponse,
    VideoListResponse,
    VideoResponse,
    VideoTranscriptResponse,
    VideoUpdate,
)


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


class VideoChapterExtractionResponse(BaseModel):
    """Created chapter count and chapter payloads."""

    count: int
    chapters: list[VideoChapterResponse]


def get_videos_facade(auth: CurrentAuth) -> VideosFacade:
    """Provide request-scoped videos facade."""
    return VideosFacade(auth.session)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_video(
    video_data: VideoCreate,
    background_tasks: BackgroundTasks,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Add a YouTube video to the library."""
    return await facade.create_video(video_data=video_data, user_id=auth.user_id, background_tasks=background_tasks)


@router.get("")
async def list_videos(
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    channel: Annotated[str | None, Query(description="Filter by channel name")] = None,
    search: Annotated[str | None, Query(description="Search in title, description, or channel")] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
) -> VideoListResponse:
    """List all YouTube videos in library with optional filtering."""
    return await facade.get_videos(
        user_id=auth.user_id,
        page=page,
        size=limit,
        channel=channel,
        search=search,
        tags=tags,
    )


@router.get("/{video_id}")
async def get_video(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Get a specific video by ID."""
    return await facade.get_video(video_id=video_id, user_id=auth.user_id)


@router.patch("/{video_id}")
async def update_video(
    video_id: uuid.UUID,
    update_data: VideoUpdate,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Update video metadata."""
    return await facade.update_video(video_id=video_id, update_data=update_data, user_id=auth.user_id)


@router.get("/{video_id}/chapters")
async def get_video_chapters(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> list[VideoChapterResponse]:
    """Get all chapters for a video."""
    return await facade.get_video_chapters(video_id=video_id, user_id=auth.user_id)


@router.get("/{video_id}/chapters/{chapter_id}")
async def get_video_chapter(
    video_id: uuid.UUID,
    chapter_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoChapterResponse:
    """Get a specific chapter for a video."""
    return await facade.get_video_chapter(video_id=video_id, chapter_id=chapter_id, user_id=auth.user_id)


@router.put("/{video_id}/chapters/{chapter_id}/status")
async def update_video_chapter_status(
    video_id: uuid.UUID,
    chapter_id: uuid.UUID,
    status_data: VideoChapterStatusUpdate,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoChapterResponse:
    """Update the status of a video chapter."""
    return await facade.update_video_chapter_status(
        video_id=video_id,
        chapter_id=chapter_id,
        chapter_status=status_data.status,
        user_id=auth.user_id,
    )


@router.post("/{video_id}/extract-chapters")
async def extract_video_chapters(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoChapterExtractionResponse:
    """Extract chapters from YouTube video."""
    chapters = await facade.extract_and_create_video_chapters(video_id=video_id, user_id=auth.user_id)
    return VideoChapterExtractionResponse(count=len(chapters), chapters=chapters)


@router.post("/{video_id}/sync-chapter-progress")
async def sync_video_chapter_progress(
    video_id: uuid.UUID,
    progress_data: VideoChapterProgressSync,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Sync chapter progress from web app to update video completion percentage."""
    return await facade.sync_chapter_progress(
        video_id=video_id,
        completed_chapter_ids=progress_data.completed_chapter_ids,
        total_chapters=progress_data.total_chapters,
        user_id=auth.user_id,
    )


@router.get("/{video_id}/transcript")
async def get_video_transcript(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoTranscriptResponse:
    """Get transcript segments with timestamps for a video."""
    return await facade.get_video_transcript_segments(video_id=video_id, user_id=auth.user_id)


@router.get("/{video_id}/details")
async def get_video_details(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoDetailsResponse:
    """Get video with chapters and transcript info in a single optimized request."""
    payload = await facade.get_video_details(video_id=video_id, user_id=auth.user_id)
    return VideoDetailsResponse.model_validate(payload)
