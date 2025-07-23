"""Video progress service for managing user-specific video progress."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.user_context import UserContext
from src.videos.models import Video, VideoProgress
from src.videos.schemas import VideoProgressResponse, VideoProgressUpdate


logger = logging.getLogger(__name__)


class VideoProgressService:
    """Service for managing user-specific video progress."""

    def __init__(self, session: AsyncSession, user_context: UserContext) -> None:
        """Initialize the video progress service.

        Args:
            session: Database session
            user_context: User context with user ID and authentication info
        """
        self.session = session
        self.user_context = user_context

    async def get_video_progress(self, video_uuid: UUID) -> VideoProgressResponse | None:
        """Get user's progress for a specific video.

        Args:
            video_uuid: Video UUID

        Returns
        -------
            VideoProgressResponse: Progress data or None if no progress exists
        """
        progress_query = select(VideoProgress).where(
            VideoProgress.video_uuid == video_uuid,
            VideoProgress.user_id == self.user_context.user_id,
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress:
            return None

        return VideoProgressResponse.model_validate(progress)

    async def update_video_progress(
        self, video_uuid: UUID, progress_data: VideoProgressUpdate
    ) -> VideoProgressResponse:
        """Update user's progress for a video.

        Args:
            video_uuid: Video UUID
            progress_data: Progress update data

        Returns
        -------
            VideoProgressResponse: Updated progress data

        Raises
        ------
            HTTPException: If video not found or update fails
        """
        try:
            # Check if video exists
            video_query = select(Video).where(Video.uuid == video_uuid)
            video_result = await self.session.execute(video_query)
            video = video_result.scalar_one_or_none()

            if not video:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Video {video_uuid} not found",
                )

            # Find or create progress record
            progress_query = select(VideoProgress).where(
                VideoProgress.video_uuid == video_uuid,
                VideoProgress.user_id == self.user_context.user_id,
            )
            progress_result = await self.session.execute(progress_query)
            progress = progress_result.scalar_one_or_none()

            if not progress:
                progress = VideoProgress(
                    video_uuid=video_uuid,
                    user_id=self.user_context.user_id,
                )
                self.session.add(progress)

            # Update progress fields
            update_data = progress_data.model_dump(exclude_unset=True, by_alias=False)
            logger.info(f"Updating video {video_uuid} progress for user {self.user_context.user_id}: {update_data}")

            for field, value in update_data.items():
                if value is not None:
                    setattr(progress, field, value)

            # Auto-calculate completion percentage if last_position is provided
            if (
                progress_data.last_position is not None
                and video.duration > 0
                and progress_data.completion_percentage is None
            ):
                completion_percentage = (progress_data.last_position / video.duration) * 100
                progress.completion_percentage = min(completion_percentage, 100.0)

            progress.last_watched_at = datetime.now(UTC)
            progress.updated_at = datetime.now(UTC)

            await self.session.commit()
            await self.session.refresh(progress)

            return VideoProgressResponse.model_validate(progress)

        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"Error updating video progress for {video_uuid}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update video progress: {e!s}",
            ) from e

    async def get_user_video_progresses(self, limit: int = 50) -> list[VideoProgressResponse]:
        """Get all video progress records for the current user.

        Args:
            limit: Maximum number of records to return

        Returns
        -------
            List of VideoProgressResponse objects
        """
        progress_query = (
            select(VideoProgress)
            .where(VideoProgress.user_id == self.user_context.user_id)
            .order_by(VideoProgress.last_watched_at.desc().nulls_last())
            .limit(limit)
        )
        progress_result = await self.session.execute(progress_query)
        progresses = progress_result.scalars().all()

        return [VideoProgressResponse.model_validate(progress) for progress in progresses]

    async def delete_video_progress(self, video_uuid: UUID) -> bool:
        """Delete user's progress for a specific video.

        Args:
            video_uuid: Video UUID

        Returns
        -------
            bool: True if progress was deleted, False if no progress existed
        """
        progress_query = select(VideoProgress).where(
            VideoProgress.video_uuid == video_uuid,
            VideoProgress.user_id == self.user_context.user_id,
        )
        progress_result = await self.session.execute(progress_query)
        progress = progress_result.scalar_one_or_none()

        if not progress:
            return False

        await self.session.delete(progress)
        await self.session.commit()
        return True
