import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db_session
from src.videos.models import Video
from src.videos.schemas import (
    VideoChapterProgressSync,
    VideoChapterResponse,
    VideoChapterStatusUpdate,
    VideoCreate,
    VideoListResponse,
    VideoProgressUpdate,
    VideoResponse,
    VideoTranscriptResponse,
    VideoUpdate,
)
from src.videos.service import video_service


logger = logging.getLogger(__name__)


def _video_to_dict(video: Video) -> dict[str, Any]:
    """Convert Video SQLAlchemy object to dict to avoid lazy loading issues."""
    return {
        "id": video.id,
        "uuid": video.uuid,
        "youtube_id": video.youtube_id,
        "url": video.url,
        "title": video.title,
        "channel": video.channel,
        "channel_id": video.channel_id,
        "duration": video.duration,
        "thumbnail_url": video.thumbnail_url,
        "description": video.description,
        "tags": video.tags,
        "archived": video.archived,
        "archived_at": video.archived_at,
        "published_at": video.published_at,
        "created_at": video.created_at,
        "updated_at": video.updated_at,
        "last_position": video.last_position,
        "completion_percentage": video.completion_percentage,
    }


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_video(
    video_data: VideoCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoResponse:
    """Add a YouTube video to the library."""
    try:
        return await video_service.create_video(db, video_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error creating video: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("")
async def list_videos(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    channel: Annotated[str | None, Query(description="Filter by channel name")] = None,
    search: Annotated[str | None, Query(description="Search in title, description, or channel")] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
) -> VideoListResponse:
    """List all YouTube videos in library with optional filtering."""
    return await video_service.get_videos(db, page=page, size=limit, channel=channel, search=search, tags=tags)


@router.get("/{video_uuid}")
async def get_video(
    video_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoResponse:
    """Get a specific video by UUID."""
    try:
        return await video_service.get_video(db, video_uuid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/{video_uuid}")
async def update_video(
    video_uuid: str,
    update_data: VideoUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoResponse:
    """Update video metadata."""
    try:
        return await video_service.update_video(db, video_uuid, update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.patch("/{video_uuid}/progress")
async def update_video_progress(
    video_uuid: str,
    progress_data: VideoProgressUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoResponse:
    """Update video watch progress."""
    try:
        return await video_service.update_progress(db, video_uuid, progress_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{video_uuid}/progress")
async def update_video_progress_post(
    video_uuid: str,
    progress_data: VideoProgressUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoResponse:
    """Update video watch progress (POST version for sendBeacon compatibility)."""
    try:
        return await video_service.update_progress(db, video_uuid, progress_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# Phase 2.3: Video Chapter Endpoints
@router.get("/{video_uuid}/chapters")
async def get_video_chapters(
    video_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[VideoChapterResponse]:
    """Get all chapters for a video."""
    try:
        return await video_service.get_video_chapters(db, video_uuid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/{video_uuid}/chapters/{chapter_id}")
async def get_video_chapter(
    video_uuid: str,
    chapter_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoChapterResponse:
    """Get a specific chapter for a video."""
    try:
        return await video_service.get_video_chapter(db, video_uuid, chapter_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.put("/{video_uuid}/chapters/{chapter_id}/status")
async def update_video_chapter_status(
    video_uuid: str,
    chapter_id: str,
    status_data: VideoChapterStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoChapterResponse:
    """Update the status of a video chapter."""
    try:
        return await video_service.update_video_chapter_status(db, video_uuid, chapter_id, status_data.status)
    except ValueError as e:
        if "Invalid status" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.post("/{video_uuid}/extract-chapters")
async def extract_video_chapters(
    video_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[VideoChapterResponse]:
    """Extract chapters from YouTube video."""
    try:
        return await video_service.extract_and_create_video_chapters(db, video_uuid)
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/{video_uuid}/sync-chapter-progress")
async def sync_video_chapter_progress(
    video_uuid: str,
    progress_data: VideoChapterProgressSync,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoResponse:
    """Sync chapter progress from frontend to update video completion percentage."""
    try:
        return await video_service.sync_chapter_progress(
            db,
            video_uuid,
            progress_data.completed_chapter_ids,
            progress_data.total_chapters,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


@router.get("/{video_uuid}/transcript")
async def get_video_transcript(
    video_uuid: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> VideoTranscriptResponse:
    """Get transcript segments with timestamps for a video."""
    try:
        return await video_service.get_video_transcript_segments(db, video_uuid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching transcript for video {video_uuid}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
