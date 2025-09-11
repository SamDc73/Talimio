import logging
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from src.auth import CurrentAuth
from src.videos.schemas import (
    VideoChapterProgressSync,
    VideoChapterResponse,
    VideoChapterStatusUpdate,
    VideoCreate,
    VideoDetailResponse,
    VideoListResponse,
    VideoProgressResponse,
    VideoProgressUpdate,
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


@router.delete("/{video_id}")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def delete_video(
    video_id: str,
    auth: CurrentAuth,
) -> None:
    """Delete a video."""
    try:
        await video_service.delete_video(db=auth.session, video_id=video_id, user_id=auth.user_id)
        await auth.session.commit()
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error deleting video {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.patch("/{video_id}/progress")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def update_video_progress(
    video_id: str,
    progress_data: VideoProgressUpdate,
    auth: CurrentAuth,
) -> VideoProgressResponse:
    """Update video watch progress.

    This endpoint is maintained for backward compatibility.
    It delegates to the unified progress system.
    """
    try:
        from uuid import UUID

        from src.progress.models import ProgressUpdate
        from src.progress.service import ProgressService

        # Convert video_id string to UUID
        try:
            video_id_uuid = UUID(video_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID format") from None

        # Build metadata for video progress
        metadata = {
            "content_type": "video",
            "last_position": progress_data.last_position,
        }

        # Add optional fields to metadata if provided
        if hasattr(progress_data, "playback_speed") and progress_data.playback_speed:
            metadata["playback_speed"] = progress_data.playback_speed
        if hasattr(progress_data, "completed_chapters") and progress_data.completed_chapters:
            metadata["completed_chapters"] = progress_data.completed_chapters

        # Use unified progress service
        service = ProgressService(auth.session)

        # Create progress update
        progress_update = ProgressUpdate(
            progress_percentage=progress_data.completion_percentage or 0.0, metadata=metadata
        )

        # Update via unified service
        result = await service.update_progress(auth.user_id, video_id_uuid, "video", progress_update)

        # Convert to legacy response format for backward compatibility
        return VideoProgressResponse(
            id=result.id,
            video_id=video_id_uuid,
            user_id=auth.user_id,
            last_position=metadata.get("last_position", 0),
            completion_percentage=result.progress_percentage,
            last_watched_at=result.updated_at,
            created_at=result.created_at,
            updated_at=result.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error updating video progress: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.get("/{video_id}/progress")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def get_video_progress(
    video_id: str,
    auth: CurrentAuth,
) -> VideoProgressResponse | None:
    """Get video watch progress.

    This endpoint is maintained for backward compatibility.
    It delegates to the unified progress system.
    """
    try:
        from uuid import UUID

        from src.progress.service import ProgressService

        # Convert video_id string to UUID
        try:
            video_id_uuid = UUID(video_id)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID format") from None

        # Use unified progress service
        service = ProgressService(auth.session)
        progress = await service.get_single_progress(auth.user_id, video_id_uuid)

        if not progress:
            # Return default response
            return VideoProgressResponse(
                id=UUID("00000000-0000-0000-0000-000000000000"),
                video_id=video_id_uuid,
                user_id=auth.user_id,
                last_position=0,
                completion_percentage=0,
                last_watched_at=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

        # Convert to legacy response format
        metadata = progress.metadata or {}
        return VideoProgressResponse(
            id=progress.id,
            video_id=video_id_uuid,
            user_id=auth.user_id,
            last_position=metadata.get("last_position", 0),
            completion_percentage=progress.progress_percentage,
            last_watched_at=metadata.get("last_watched_at", progress.updated_at),
            created_at=progress.created_at,
            updated_at=progress.updated_at,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error getting video progress: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/{video_id}/progress")
# @api_rate_limit  # TODO: Enable rate limiting with request parameter
async def update_video_progress_post(
    video_id: str,
    progress_data: VideoProgressUpdate,
    auth: CurrentAuth,
) -> VideoProgressResponse:
    """Update video watch progress (POST version for sendBeacon compatibility).

    This endpoint is maintained for backward compatibility.
    It delegates to the unified progress system.
    """
    # Delegate to the PATCH endpoint handler
    return await update_video_progress(video_id, progress_data, auth)


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
) -> VideoDetailResponse:
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
            progress = await video_service.get_video_progress(auth.session, video_id, auth.user_id)
        except Exception:
            progress = None

        # Build response
        return VideoDetailResponse(
            **video.model_dump(), chapters=chapters, transcript_info=transcript_info, progress=progress
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.exception(f"Error fetching video details for {video_id}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
