"""Videos Module Facade.

Single entry point for all video-related operations.
Coordinates internal video services and provides stable API for other modules.
"""

import logging
from typing import Any
from uuid import UUID

from .service import VideoService
from .services.video_progress_service import VideoProgressService


logger = logging.getLogger(__name__)


class VideosFacade:
    """
    Single entry point for all video operations.

    Coordinates internal video services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Internal services - not exposed to outside modules
        self._video_service = VideoService()
        self._progress_service = VideoProgressService()  # Implements ProgressTracker protocol

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get video with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_video(content_id, user_id)

    async def get_video(self, video_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get complete video information with progress.

        Coordinates video service and progress service to provide comprehensive data.
        """
        try:
            # Get video information - need to pass user_id as well
            # Create a temporary session for the video service call
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                video_response = await self._video_service.get_video(session, str(video_id), user_id)
                # Convert response to dict
                video = video_response.model_dump() if video_response else None

            if not video:
                return {"error": "Video not found"}

            # Get progress information
            progress = await self._progress_service.get_progress(video_id, user_id)

            # Build response
            return {
                "video": video,
                "progress": progress,
                "completion_percentage": progress.get("completion_percentage", 0),
                "last_position": progress.get("last_position", 0),
                "total_duration": video.get("duration", 0),
                "playback_speed": progress.get("playback_speed", 1.0),
                "success": True,
            }

        except Exception as e:
            logger.exception(f"Error getting video {video_id} for user {user_id}: {e}")
            return {"error": "Failed to retrieve video"}

    # NOTE: create_content and create_video methods removed - router uses service directly

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update video watching progress via ContentFacade contract."""
        return await self.update_video_progress(content_id, user_id, progress_data)

    async def update_video_progress(
        self, video_id: UUID, user_id: UUID, progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update video watching progress.

        Handles progress updates, position tracking, and completion detection.
        """
        try:
            # Update progress using the progress tracker
            updated_progress = await self._progress_service.update_progress(video_id, user_id, progress_data)

            if "error" in updated_progress:
                return {"error": updated_progress["error"], "success": False}

            return {"progress": updated_progress, "success": True}

        except Exception as e:
            logger.exception(f"Error updating progress for video {video_id}: {e}")
            return {"error": "Failed to update progress", "success": False}


videos_facade = VideosFacade()
