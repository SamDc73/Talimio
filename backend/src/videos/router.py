import logging
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from src.auth import CurrentAuth
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
from src.videos.service import video_service


logger = logging.getLogger(__name__)


router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", status_code=status.HTTP_201_CREATED)
# @upload_rate_limit  # TODO: Enable rate limiting with request parameter
async def create_video(
    video_data: VideoCreate,
    background_tasks: BackgroundTasks,
    auth: CurrentAuth,
) -> VideoResponse:
    """Add a YouTube video to the library."""
    try:
        return await video_service.create_video(
            db=auth.session, video_data=video_data, background_tasks=background_tasks, user_id=auth.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error creating video: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def list_videos(
    auth: CurrentAuth,
    page: Annotated[int, Query(ge=1, description="Page number")] = 1,
    limit: Annotated[int, Query(ge=1, le=100, description="Items per page")] = 20,
    channel: Annotated[str | None, Query(description="Filter by channel name")] = None,
    search: Annotated[str | None, Query(description="Search in title, description, or channel")] = None,
    tags: Annotated[list[str] | None, Query(description="Filter by tags")] = None,
) -> VideoListResponse:
    """List all YouTube videos in library with optional filtering."""
    try:
        return await video_service.get_videos(
            db=auth.session, user_id=auth.user_id, page=page, size=limit, channel=channel, search=search, tags=tags
        )
    except Exception as e:
        logger.exception(f"Error listing videos: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{video_id}")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def get_video(
    video_id: str,
    auth: CurrentAuth,
) -> VideoResponse:
    """Get a specific video by ID."""
    try:
        return await video_service.get_video(db=auth.session, video_id=video_id, user_id=auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.patch("/{video_id}")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def update_video(
    video_id: str,
    update_data: VideoUpdate,
    auth: CurrentAuth,
) -> VideoResponse:
    """Update video metadata."""
    try:
        return await video_service.update_video(
            db=auth.session, video_id=video_id, update_data=update_data, user_id=auth.user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error updating video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e




@router.get("/{video_id}/chapters")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def get_video_chapters(
    video_id: str,
    auth: CurrentAuth,
) -> list[VideoChapterResponse]:
    """Get all chapters for a video."""
    try:
        return await video_service.get_video_chapters(auth.session, video_id, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching chapters for video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{video_id}/chapters/{chapter_id}")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def get_video_chapter(
    video_id: str,
    chapter_id: str,
    auth: CurrentAuth,
) -> VideoChapterResponse:
    """Get a specific chapter for a video."""
    try:
        return await video_service.get_video_chapter(auth.session, video_id, chapter_id, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching chapter {chapter_id} for video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.put("/{video_id}/chapters/{chapter_id}/status")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def update_video_chapter_status(
    video_id: str,
    chapter_id: str,
    status_data: VideoChapterStatusUpdate,
    auth: CurrentAuth,
) -> VideoChapterResponse:
    """Update the status of a video chapter."""
    try:
        return await video_service.update_video_chapter_status(
            auth.session, video_id, chapter_id, status_data.status, auth.user_id
        )
    except ValueError as e:
        if "Invalid status" in str(e):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error updating chapter {chapter_id} status for video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/{video_id}/extract-chapters")
# @ai_rate_limit  # TODO: Enable rate limiting with request parameter
async def extract_video_chapters(
    video_id: str,
    auth: CurrentAuth,
) -> dict[str, Any]:
    """Extract chapters from YouTube video."""
    try:
        chapters = await video_service.extract_and_create_video_chapters(auth.session, video_id, auth.user_id)
        return {"count": len(chapters), "chapters": chapters}
    except ValueError as e:
        if "not found" in str(e):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error extracting chapters for video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/{video_id}/sync-chapter-progress")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def sync_video_chapter_progress(
    video_id: str,
    progress_data: VideoChapterProgressSync,
    auth: CurrentAuth,
) -> VideoResponse:
    """Sync chapter progress from web app to update video completion percentage."""
    try:
        return await video_service.sync_chapter_progress(
            auth.session,
            video_id,
            progress_data.completed_chapter_ids,
            progress_data.total_chapters,
            user_id=auth.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error syncing chapter progress for video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{video_id}/transcript")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def get_video_transcript(
    video_id: str,
    auth: CurrentAuth,
) -> VideoTranscriptResponse:
    """Get transcript segments with timestamps for a video."""
    try:
        return await video_service.get_video_transcript_segments(auth.session, video_id, auth.user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching transcript for video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{video_id}/details")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def get_video_details(
    video_id: str,
    auth: CurrentAuth,
) -> dict[str, Any]:
    """Get video with chapters and transcript info in a single optimized request."""
    try:
        # Get video
        video = await video_service.get_video(auth.session, video_id, auth.user_id)

        # Get chapters
        try:
            chapters = await video_service.get_video_chapters(auth.session, video_id, auth.user_id)
        except Exception:
            chapters = []

        # Get transcript info (not the full segments, just metadata)
        transcript_info = await video_service.get_transcript_info(auth.session, video_id)

        # Get progress
        try:
            from src.videos.facade import videos_facade
            progress_result = await videos_facade.get_video(UUID(video_id), auth.user_id)
            progress = progress_result.get("progress") if progress_result.get("success") else None
        except Exception:
            progress = None

        # Build response
        return {
            **video.model_dump(),
            "chapters": chapters,
            "transcript_info": transcript_info,
            "progress": progress
        }

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching video details for {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
