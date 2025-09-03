"""Video content service for video-specific operations."""

import json
import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import async_session_maker
from src.videos.models import Video


logger = logging.getLogger(__name__)


class VideoContentService:
    """Video service handling video-specific content operations."""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self.session = session

    async def create_video(self, data: dict, user_id: UUID) -> Video:
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

    async def delete_video(self, video_id: UUID, user_id: UUID) -> bool:
        """Delete a video."""
        async with async_session_maker() as session:
            # Get the video
            query = select(Video).where(Video.id == video_id, Video.user_id == user_id)
            result = await session.execute(query)
            video = result.scalar_one_or_none()

            if not video:
                return False

            # Delete the video (cascade will handle related records)
            await session.delete(video)
            await session.commit()

            logger.info(f"Deleted video {video_id}")
            return True
