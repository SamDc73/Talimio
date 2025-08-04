"""Video content service extending BaseContentService."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.base_service import BaseContentService
from src.database.session import async_session_maker
from src.videos.models import Video


logger = logging.getLogger(__name__)


class VideoContentService(BaseContentService):
    """Video service with shared content behavior."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        super().__init__()
        self.session = session

    def _get_content_type(self) -> str:
        """Return the content type for this service."""
        return "video"

    async def _do_create(self, data: dict, user_id: UUID) -> Video:
        """Create a new video."""
        async with async_session_maker() as session:
            # Convert tags to JSON if present
            if "tags" in data and data["tags"] is not None:
                data["tags"] = json.dumps(data["tags"])

            # Create video instance
            video = Video(**data, user_id=user_id, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))

            session.add(video)
            await session.commit()
            await session.refresh(video)

            logger.info(f"Created video {video.id} for user {user_id}")
            return video

    async def _do_update(self, content_id: UUID, data: dict, user_id: UUID) -> Video:
        """Update an existing video."""
        async with async_session_maker() as session:
            # Get the video
            query = select(Video).where(Video.id == content_id, Video.user_id == user_id)
            result = await session.execute(query)
            video = result.scalar_one_or_none()

            if not video:
                error_msg = f"Video {content_id} not found"
                raise ValueError(error_msg)

            # Update fields
            for field, value in data.items():
                if (field == "tags" and value is not None) or (field == "chapters" and value is not None):
                    setattr(video, field, json.dumps(value))
                else:
                    setattr(video, field, value)

            video.updated_at = datetime.now(UTC)

            await session.commit()
            await session.refresh(video)

            logger.info(f"Updated video {video.id}")
            return video

    async def _do_delete(self, content_id: UUID, user_id: UUID) -> bool:
        """Delete a video."""
        async with async_session_maker() as session:
            # Get the video
            query = select(Video).where(Video.id == content_id, Video.user_id == user_id)
            result = await session.execute(query)
            video = result.scalar_one_or_none()

            if not video:
                return False

            # Delete the video (cascade will handle related records)
            await session.delete(video)
            await session.commit()

            logger.info(f"Deleted video {content_id}")
            return True

    def _needs_ai_processing(self, content: Video) -> bool:
        """Check if video needs AI processing after creation."""
        # Videos need AI processing for transcript generation
        return content.transcript_status != "completed"

    def _needs_ai_reprocessing(self, _content: Video, updated_data: dict) -> bool:
        """Check if video needs AI reprocessing after update."""
        # Reprocess if URL changes
        return "url" in updated_data

    async def _update_progress(self, content_id: UUID, _user_id: UUID, status: str) -> None:
        """Update progress tracking for video."""
        try:
            # For videos, we track watch progress separately
            # This is just for creation status
            logger.info(f"Video {content_id} status: {status}")
        except Exception as e:
            logger.exception(f"Failed to update video progress: {e}")
