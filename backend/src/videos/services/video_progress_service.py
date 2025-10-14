"""Video progress service implementing the ProgressTracker protocol.

This provides a simplified interface for progress tracking that doesn't
depend on UserContext or session management.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.database.session import async_session_maker
from src.progress.models import ProgressUpdate
from src.progress.protocols import ProgressTracker
from src.progress.service import ProgressService
from src.videos.models import Video


logger = logging.getLogger(__name__)


class VideoProgressService(ProgressTracker):
    """Simplified progress service for videos that implements the ProgressTracker protocol."""

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific video and user."""
        async with async_session_maker() as session:
            # Use unified progress service
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, content_id)

            if not progress_data:
                return {"last_position": 0, "completion_percentage": 0, "playback_speed": 1.0, "completed_chapters": []}

            # Get metadata from unified progress
            metadata = progress_data.metadata or {}

            # Get video duration for accurate percentage calculation if needed
            completion_percentage = progress_data.progress_percentage
            last_position = metadata.get("last_position", 0)


            return {
                "id": progress_data.id,
                "last_position": last_position,
                "completion_percentage": completion_percentage,
                "playback_speed": metadata.get("playback_speed", 1.0),
                "completed_chapters": metadata.get("completed_chapters", []),
                "last_watched_at": metadata.get("last_watched_at", progress_data.updated_at),
                "created_at": progress_data.created_at,
                "updated_at": progress_data.updated_at,
            }

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update progress data for specific video and user."""
        async with async_session_maker() as session:
            # Check if video exists
            video_query = select(Video).where(Video.id == content_id)
            video_result = await session.execute(video_query)
            video = video_result.scalar_one_or_none()

            if not video:
                logger.error(f"Video {content_id} not found")
                return {"error": "Video not found"}

            # Get current progress to merge metadata
            progress_service = ProgressService(session)
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            # Merge existing metadata with new data
            existing_metadata = current_progress.metadata if current_progress else {}
            metadata = {
                **existing_metadata,
                "content_type": "video",
                "duration": video.duration or 0,
                "last_watched_at": datetime.now(UTC).isoformat(),
            }

            # Update video-specific fields in metadata
            if "last_position" in progress_data and progress_data["last_position"] is not None:
                metadata["last_position"] = progress_data["last_position"]

            if "playback_speed" in progress_data:
                metadata["playback_speed"] = progress_data["playback_speed"]

            if "completed_chapters" in progress_data:
                metadata["completed_chapters"] = progress_data["completed_chapters"]

            # Calculate completion percentage (simplified)
            if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
                completion_percentage = progress_data["completion_percentage"]
            else:
                completion_percentage = current_progress.progress_percentage if current_progress else 0

            # Update using unified progress service
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)

            updated = await progress_service.update_progress(user_id, content_id, "video", progress_update)

            # Return updated progress in expected format
            return {
                "id": updated.id,
                "last_position": metadata.get("last_position", 0),
                "completion_percentage": updated.progress_percentage,
                "last_watched_at": metadata.get("last_watched_at"),
                "created_at": updated.created_at,
                "updated_at": updated.updated_at,
            }

    async def calculate_completion_percentage(self, content_id: UUID, user_id: UUID) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        progress = await self.get_progress(content_id, user_id)
        return progress.get("completion_percentage", 0.0)

    async def initialize_progress(self, content_id: UUID, user_id: UUID, total_duration: float | None = None) -> None:
        """Initialize progress tracking for a video."""
        async with async_session_maker() as session:
            # Check if progress already exists
            progress_service = ProgressService(session)
            existing = await progress_service.get_single_progress(user_id, content_id)

            if not existing:
                # Create initial progress with metadata
                metadata = {
                    "content_type": "video",
                    "last_position": 0,
                    "playback_speed": 1.0,
                    "completed_chapters": [],
                    "duration": total_duration or 0,
                    "last_watched_at": datetime.now(UTC).isoformat(),
                }

                progress_update = ProgressUpdate(progress_percentage=0.0, metadata=metadata)

                await progress_service.update_progress(user_id, content_id, "video", progress_update)

    async def update_playback_settings(
        self, content_id: UUID, user_id: UUID, settings: dict[str, Any]
    ) -> dict[str, Any]:
        """Update playback settings for a video."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            if current_progress:
                metadata = current_progress.metadata.copy()
                metadata.update(settings)

                progress_update = ProgressUpdate(
                    progress_percentage=current_progress.progress_percentage, metadata=metadata
                )

                await progress_service.update_progress(user_id, content_id, "video", progress_update)

            return settings

