"""Videos Module Facade.

Single entry point for all video-related operations.
Coordinates internal video services and provides stable API for other modules.
"""

import logging
import uuid
from typing import Any

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from .schemas import (
    VideoChapterResponse,
    VideoCreate,
    VideoLearningStatus,
    VideoListResponse,
    VideoResponse,
    VideoTranscriptResponse,
    VideoUpdate,
)
from .service import VideoNotFoundError, VideoService
from .services.video_progress_service import VideoProgressService


logger = logging.getLogger(__name__)


class VideosFacade:
    """
    Single entry point for all video operations.

    Coordinates internal video services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._video_service = VideoService()
        self._progress_service = VideoProgressService(session)

    async def get_content_with_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """
        Get video with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_video_with_progress(content_id, user_id)

    async def create_video(self, video_data: VideoCreate, user_id: uuid.UUID) -> VideoResponse:
        """Create a video record for the authenticated user."""
        return await self._video_service.create_video(self._session, video_data, user_id)

    async def get_videos(
        self,
        user_id: uuid.UUID,
        page: int = 1,
        size: int = 20,
        channel: str | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> VideoListResponse:
        """List user videos with filtering and pagination."""
        return await self._video_service.get_videos(
            self._session,
            user_id=user_id,
            page=page,
            size=size,
            channel=channel,
            search=search,
            tags=tags,
        )

    async def get_video(self, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoResponse:
        """Get a single video with ownership checks."""
        return await self._video_service.get_video(self._session, video_id, user_id)

    async def update_video(self, video_id: uuid.UUID, update_data: VideoUpdate, user_id: uuid.UUID) -> VideoResponse:
        """Update a single video owned by the authenticated user."""
        return await self._video_service.update_video(self._session, video_id, update_data, user_id)

    async def get_video_chapters(self, video_id: uuid.UUID, user_id: uuid.UUID) -> list[VideoChapterResponse]:
        """Get chapters for a specific video."""
        return await self._video_service.get_video_chapters(self._session, video_id, user_id)

    async def get_video_chapter(
        self, video_id: uuid.UUID, chapter_id: uuid.UUID, user_id: uuid.UUID
    ) -> VideoChapterResponse:
        """Get one chapter for a specific video."""
        return await self._video_service.get_video_chapter(self._session, video_id, chapter_id, user_id)

    async def update_video_chapter_status(
        self,
        video_id: uuid.UUID,
        chapter_id: uuid.UUID,
        chapter_status: VideoLearningStatus,
        user_id: uuid.UUID,
    ) -> VideoChapterResponse:
        """Update chapter learning status for a video."""
        return await self._video_service.update_video_chapter_status(
            self._session,
            video_id,
            chapter_id,
            chapter_status,
            user_id,
        )

    async def extract_and_create_video_chapters(
        self, video_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[VideoChapterResponse]:
        """Extract chapters and persist them for a video."""
        return await self._video_service.extract_and_create_video_chapters(self._session, video_id, user_id)

    async def sync_chapter_progress(
        self,
        video_id: uuid.UUID,
        completed_chapter_ids: list[uuid.UUID],
        total_chapters: int,
        user_id: uuid.UUID,
    ) -> VideoResponse:
        """Sync chapter completion payload into unified progress."""
        return await self._video_service.sync_chapter_progress(
            self._session,
            video_id,
            completed_chapter_ids,
            total_chapters,
            user_id=user_id,
        )

    async def get_video_transcript_segments(self, video_id: uuid.UUID, user_id: uuid.UUID) -> VideoTranscriptResponse:
        """Get transcript segments for a video."""
        return await self._video_service.get_video_transcript_segments(self._session, video_id, user_id)

    async def get_transcript_info(self, video_id: uuid.UUID) -> dict[str, Any] | None:
        """Get transcript metadata without loading transcript segments."""
        return await self._video_service.get_transcript_info(self._session, video_id)

    async def get_video_with_progress(self, video_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, Any]:
        """
        Get complete video information with progress.

        Coordinates video service and progress service to provide comprehensive data.
        """
        try:
            video_response = await self._video_service.get_video(self._session, video_id, user_id)
            video = video_response.model_dump()
            progress = await self._progress_service.get_progress(video_id, user_id)
        except VideoNotFoundError:
            raise
        except (ValueError, RuntimeError, SQLAlchemyError, TypeError):
            logger.exception("videos.get.failed", extra={"video_id": str(video_id), "user_id": str(user_id)})
            raise

        return {
            "video": video,
            "progress": progress,
            "completion_percentage": progress.get("completion_percentage", 0),
            "last_position": progress.get("last_position", 0),
            "total_duration": video.get("duration", 0),
            "playback_speed": progress.get("playback_speed", 1.0),
        }

    async def update_progress(self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update video watching progress via ContentFacade contract."""
        return await self.update_video_progress(content_id, user_id, progress_data)

    async def update_video_progress(
        self, video_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update video watching progress.

        Handles progress updates, position tracking, and completion detection.
        """
        try:
            updated_progress = await self._progress_service.update_progress(video_id, user_id, progress_data)
        except (ValueError, RuntimeError, SQLAlchemyError, TypeError):
            logger.exception("videos.progress.update_failed", extra={"video_id": str(video_id)})
            raise

        return {"progress": updated_progress}
