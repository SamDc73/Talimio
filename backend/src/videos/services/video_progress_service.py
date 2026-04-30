
import uuid

from sqlalchemy.ext.asyncio import AsyncSession


"""Video progress service implementing the ProgressTracker protocol.

This provides a simplified interface for progress tracking that doesn't
depend on request-scoped auth context or router-layer dependencies.
"""


import logging
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy import select

from src.exceptions import NotFoundError
from src.progress.models import ProgressUpdate
from src.progress.protocols import ProgressTracker
from src.progress.service import ProgressService
from src.videos.models import Video


logger = logging.getLogger(__name__)


class VideoProgressService(ProgressTracker):
    """Simplified progress service for videos that implements the ProgressTracker protocol."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> dict[str, object]:
        """Get progress data for specific video and user."""
        # Use unified progress service
        progress_service = ProgressService(self._session)
        progress_data = await progress_service.get_single_progress(user_id, content_id)

        if not progress_data:
            return {"last_position": 0, "completion_percentage": 0, "playback_speed": 1.0, "completed_chapters": []}

        # Get metadata from unified progress
        metadata: dict[str, JsonValue] = dict(progress_data.metadata or {})

        # Get video duration for accurate percentage calculation if needed
        completion_percentage = progress_data.progress_percentage
        last_position = metadata.get("last_position", 0)

        return {
            "last_position": last_position,
            "completion_percentage": completion_percentage,
            "playback_speed": metadata.get("playback_speed", 1.0),
            "completed_chapters": metadata.get("completed_chapters", []),
            "id": str(progress_data.id) if progress_data.id is not None else None,
            "last_watched_at": metadata.get(
                "last_watched_at", progress_data.updated_at.isoformat() if progress_data.updated_at else None
            ),
            "created_at": progress_data.created_at.isoformat() if progress_data.created_at else None,
            "updated_at": progress_data.updated_at.isoformat() if progress_data.updated_at else None,
        }

    async def update_progress(
        self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: dict[str, object]
    ) -> dict[str, object]:
        """Update progress data for specific video and user."""
        # Check if video exists
        video_query = select(Video).where(Video.id == content_id)
        video_result = await self._session.execute(video_query)
        video = video_result.scalar_one_or_none()

        if not video:
            logger.warning("videos.progress.not_found", extra={"content_id": str(content_id)})
            resource_type = "video"
            raise NotFoundError(resource_type, str(content_id))

        # Get current progress to merge metadata
        progress_service = ProgressService(self._session)
        current_progress = await progress_service.get_single_progress(user_id, content_id)

        # Merge existing metadata with new data
        existing_metadata: dict[str, JsonValue] = dict(current_progress.metadata or {}) if current_progress else {}
        metadata: dict[str, JsonValue] = {
            **existing_metadata,
            "content_type": "video",
            "duration": video.duration or 0,
            "last_watched_at": datetime.now(UTC).isoformat(),
        }

        # Update video-specific fields in metadata
        if "last_position" in progress_data and progress_data["last_position"] is not None:
            metadata["last_position"] = cast("JsonValue", progress_data["last_position"])

        if "playback_speed" in progress_data:
            metadata["playback_speed"] = cast("JsonValue", progress_data["playback_speed"])

        if "completed_chapters" in progress_data:
            metadata["completed_chapters"] = cast("JsonValue", progress_data["completed_chapters"])

        # Calculate completion percentage (simplified)
        if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
            requested_percentage = progress_data["completion_percentage"]
            completion_percentage = requested_percentage if isinstance(requested_percentage, (int, float)) else 0
        else:
            completion_percentage = current_progress.progress_percentage if current_progress else 0

        # Update using unified progress service
        progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)

        updated = await progress_service.update_progress(user_id, content_id, "video", progress_update)

        # Return updated progress in expected format
        return {
            "id": str(updated.id) if updated.id is not None else None,
            "last_position": metadata.get("last_position", 0),
            "completion_percentage": updated.progress_percentage,
            "last_watched_at": metadata.get("last_watched_at"),
            "created_at": updated.created_at.isoformat() if updated.created_at else None,
            "updated_at": updated.updated_at.isoformat() if updated.updated_at else None,
        }

    async def calculate_completion_percentage(self, content_id: uuid.UUID, user_id: uuid.UUID) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        progress = await self.get_progress(content_id, user_id)
        completion_percentage = progress.get("completion_percentage", 0.0)
        return float(completion_percentage) if isinstance(completion_percentage, (int, float)) else 0.0

    async def initialize_progress(self, content_id: uuid.UUID, user_id: uuid.UUID, total_duration: float | None = None) -> None:
        """Initialize progress tracking for a video."""
        # Check if progress already exists
        progress_service = ProgressService(self._session)
        existing = await progress_service.get_single_progress(user_id, content_id)

        if not existing:
            # Create initial progress with metadata
            metadata: dict[str, JsonValue] = {
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
        self, content_id: uuid.UUID, user_id: uuid.UUID, settings: dict[str, JsonValue]
    ) -> dict[str, JsonValue]:
        """Update playback settings for a video."""
        progress_service = ProgressService(self._session)
        current_progress = await progress_service.get_single_progress(user_id, content_id)

        if current_progress:
            metadata = current_progress.metadata.copy()
            metadata.update(settings)

            progress_update = ProgressUpdate(
                progress_percentage=current_progress.progress_percentage, metadata=metadata
            )

            await progress_service.update_progress(user_id, content_id, "video", progress_update)

        return settings
