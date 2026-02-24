import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError

from src.auth import CurrentAuth
from src.videos.facade import VideosFacade
from src.videos.schemas import (
    VideoChapterProgressSync,
    VideoChapterResponse,
    VideoChapterStatusUpdate,
    VideoCreate,
    VideoListResponse,
    VideoResponse,
    VideoTranscriptResponse,
    VideoUpdate,
)
from src.videos.service import VideoChapterNotFoundError, VideoNotFoundError


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


def get_videos_facade(auth: CurrentAuth) -> VideosFacade:
    """Provide request-scoped videos facade."""
    return VideosFacade(auth.session)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_video(
    video_data: VideoCreate,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Add a YouTube video to the library."""
    try:
        return await facade.create_video(video_data=video_data, user_id=auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error creating video: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create video") from e


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
    try:
        return await facade.get_videos(
            user_id=auth.user_id,
            page=page,
            size=limit,
            channel=channel,
            search=search,
            tags=tags,
        )
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error listing videos: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to list videos") from e


@router.get("/{video_id}")
async def get_video(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Get a specific video by ID."""
    try:
        return await facade.get_video(video_id=video_id, user_id=auth.user_id)
    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error fetching video %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve video") from e


@router.patch("/{video_id}")
async def update_video(
    video_id: uuid.UUID,
    update_data: VideoUpdate,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Update video metadata."""
    try:
        return await facade.update_video(video_id=video_id, update_data=update_data, user_id=auth.user_id)
    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error updating video %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update video") from e


@router.get("/{video_id}/chapters")
async def get_video_chapters(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> list[VideoChapterResponse]:
    """Get all chapters for a video."""
    try:
        return await facade.get_video_chapters(video_id=video_id, user_id=auth.user_id)
    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error fetching chapters for video %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve video chapters") from e


@router.get("/{video_id}/chapters/{chapter_id}")
async def get_video_chapter(
    video_id: uuid.UUID,
    chapter_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoChapterResponse:
    """Get a specific chapter for a video."""
    try:
        return await facade.get_video_chapter(video_id=video_id, chapter_id=chapter_id, user_id=auth.user_id)
    except (VideoNotFoundError, VideoChapterNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error fetching chapter %s for video %s: %s", chapter_id, video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve video chapter") from e


@router.put("/{video_id}/chapters/{chapter_id}/status")
async def update_video_chapter_status(
    video_id: uuid.UUID,
    chapter_id: uuid.UUID,
    status_data: VideoChapterStatusUpdate,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoChapterResponse:
    """Update the status of a video chapter."""
    try:
        return await facade.update_video_chapter_status(
            video_id=video_id,
            chapter_id=chapter_id,
            chapter_status=status_data.status,
            user_id=auth.user_id,
        )
    except (VideoNotFoundError, VideoChapterNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error updating chapter %s status for video %s: %s", chapter_id, video_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update video chapter status",
        ) from e


@router.post("/{video_id}/extract-chapters")
async def extract_video_chapters(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> dict[str, Any]:
    """Extract chapters from YouTube video."""
    try:
        chapters = await facade.extract_and_create_video_chapters(video_id=video_id, user_id=auth.user_id)
        return {"count": len(chapters), "chapters": chapters}
    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error extracting chapters for video %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to extract video chapters") from e


@router.post("/{video_id}/sync-chapter-progress")
async def sync_video_chapter_progress(
    video_id: uuid.UUID,
    progress_data: VideoChapterProgressSync,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoResponse:
    """Sync chapter progress from web app to update video completion percentage."""
    try:
        return await facade.sync_chapter_progress(
            video_id=video_id,
            completed_chapter_ids=progress_data.completed_chapter_ids,
            total_chapters=progress_data.total_chapters,
            user_id=auth.user_id,
        )
    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error syncing chapter progress for video %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to sync chapter progress") from e


@router.get("/{video_id}/transcript")
async def get_video_transcript(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> VideoTranscriptResponse:
    """Get transcript segments with timestamps for a video."""
    try:
        return await facade.get_video_transcript_segments(video_id=video_id, user_id=auth.user_id)
    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error fetching transcript for video %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve video transcript") from e


@router.get("/{video_id}/details")
async def get_video_details(
    video_id: uuid.UUID,
    auth: CurrentAuth,
    facade: Annotated[VideosFacade, Depends(get_videos_facade)],
) -> dict[str, Any]:
    """Get video with chapters and transcript info in a single optimized request."""
    try:
        video = await facade.get_video(video_id=video_id, user_id=auth.user_id)
        chapters = await facade.get_video_chapters(video_id=video_id, user_id=auth.user_id)
        transcript_info = await facade.get_transcript_info(video_id=video_id)
        progress_result = await facade.get_video_with_progress(video_id, auth.user_id)
        if progress_result.get("success") is not True:
            progress_error = progress_result.get("error")
            if not isinstance(progress_error, str) or not progress_error.strip():
                msg = "Video progress retrieval failed without a specific error detail"
                raise RuntimeError(msg)
            raise RuntimeError(progress_error)

        if "progress" not in progress_result:
            msg = "Video progress payload missing from successful response"
            raise RuntimeError(msg)
        progress = progress_result["progress"]

        return {
            **video.model_dump(),
            "chapters": chapters,
            "transcript_info": transcript_info,
            "progress": progress,
        }

    except VideoNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except (RuntimeError, SQLAlchemyError) as e:
        logger.exception("Error fetching video details for %s: %s", video_id, e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to retrieve video details") from e
