"""Video content processor for tag generation."""

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.videos.models import Video


logger = logging.getLogger(__name__)


class VideoProcessor:
    """Processor for extracting video content for tagging."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize video processor.

        Args:
            session: Database session
        """
        self.session = session

    async def extract_content_for_tagging(
        self,
        video: Video,
    ) -> dict[str, str]:
        """Extract video content for tag generation.

        Args:
            video: Video model instance

        Returns
        -------
            Dictionary with title, channel, and content_preview
        """
        # Build content preview from available metadata
        content_parts = []

        # Add channel information
        content_parts.append(f"Channel: {video.channel}")

        # Add description if available
        if video.description:
            # Take first 1000 characters of description
            description_preview = video.description[:1000]
            if len(video.description) > 1000:
                description_preview += "..."
            content_parts.append(f"Description: {description_preview}")

        # Add duration information (can help identify tutorial vs lecture)
        if video.duration:
            duration_minutes = video.duration // 60
            if duration_minutes < 10:
                content_parts.append("Duration: Short video (< 10 minutes)")
            elif duration_minutes < 30:
                content_parts.append("Duration: Medium video (10-30 minutes)")
            else:
                content_parts.append(f"Duration: Long video ({duration_minutes} minutes)")

        # Add existing tags if any
        if video.tags:
            try:
                existing_tags = json.loads(video.tags)
                if existing_tags:
                    content_parts.append(f"YouTube tags: {', '.join(existing_tags[:10])}")
            except Exception as e:
                logger.debug(f"Failed to parse existing video tags: {e}")

        # TODO: In the future, could add:
        # - Transcript extraction from YouTube API
        # - Caption/subtitle analysis
        # - Video metadata from YouTube Data API

        return {
            "title": video.title,
            "channel": video.channel,
            "content_preview": "\n\n".join(content_parts),
        }


async def process_video_for_tagging(
    video_id: UUID,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process a video to extract content for tagging.

    Args:
        video_id: UUID of the video to process
        session: Database session

    Returns
    -------
        Dictionary with title, channel, and content_preview, or None if not found
    """
    # Get video from database
    result = await session.execute(
        select(Video).where(Video.id == video_id),
    )
    video = result.scalar_one_or_none()

    if not video:
        logger.error(f"Video not found: {video_id}")
        return None

    # Process video
    processor = VideoProcessor(session)
    return await processor.extract_content_for_tagging(video)
