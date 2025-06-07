import json
import logging
from datetime import datetime
from typing import Any

import yt_dlp
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.pagination import Paginator
from src.videos.models import Video, VideoChapter
from src.videos.schemas import (
    VideoChapterResponse,
    VideoCreate,
    VideoListResponse,
    VideoProgressUpdate,
    VideoResponse,
    VideoUpdate,
)


logger = logging.getLogger(__name__)


class VideoService:
    """Service for managing videos."""

    async def create_video(self, db: AsyncSession, video_data: VideoCreate) -> VideoResponse:
        """Create a new video by fetching metadata from YouTube."""
        # Extract video info using yt-dlp
        video_info = await self._fetch_video_info(video_data.url)

        # Check if video already exists
        existing = await db.execute(
            select(Video).where(Video.youtube_id == video_info["youtube_id"]),
        )
        existing_video = existing.scalar_one_or_none()
        if existing_video:
            # Return existing video instead of throwing error
            return VideoResponse.model_validate(existing_video)

        # Create video record
        video = Video(
            youtube_id=video_info["youtube_id"],
            url=video_info["url"],
            title=video_info["title"],
            channel=video_info["channel"],
            channel_id=video_info["channel_id"],
            duration=video_info["duration"],
            thumbnail_url=video_info.get("thumbnail_url"),
            description=video_info.get("description"),
            tags=json.dumps(video_info.get("tags", [])),
            published_at=video_info.get("published_at"),
        )

        db.add(video)
        await db.commit()
        await db.refresh(video)

        # Trigger automatic tagging
        try:
            from src.ai.client import ModelManager
            from src.tagging.service import TaggingService

            model_manager = ModelManager()
            tagging_service = TaggingService(db, model_manager)

            # Build content preview
            content_preview = []
            content_preview.append(f"Channel: {video.channel}")

            if video.description:
                # Take first 1000 characters
                desc_preview = video.description[:1000]
                if len(video.description) > 1000:
                    desc_preview += "..."
                content_preview.append(f"Description: {desc_preview}")

            # Add YouTube tags if available
            if video_info.get("tags"):
                content_preview.append(f"YouTube tags: {', '.join(video_info['tags'][:10])}")

            # Generate and store tags
            tags = await tagging_service.tag_content(
                content_id=video.uuid,
                content_type="video",
                title=video.title,
                content_preview="\n\n".join(content_preview),
            )

            # Update video's tags field with both YouTube and generated tags
            if tags:
                existing_tags = video_info.get("tags", [])
                all_tags = list(set(existing_tags + tags))  # Combine and deduplicate
                video.tags = json.dumps(all_tags)
                await db.commit()

            logger.info(f"Successfully tagged video {video.uuid} with tags: {tags}")

        except Exception as e:
            # Don't fail video creation if tagging fails
            logger.exception(f"Failed to tag video {video.uuid}: {e}")

        return VideoResponse.model_validate(video)

    async def get_videos(
        self,
        db: AsyncSession,
        page: int = 1,
        size: int = 20,
        channel: str | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> VideoListResponse:
        """Get paginated list of videos with optional filtering."""
        query = select(Video)

        # Apply filters
        filters = []
        if channel:
            filters.append(Video.channel.ilike(f"%{channel}%"))

        if search:
            filters.append(
                or_(
                    Video.title.ilike(f"%{search}%"),
                    Video.description.ilike(f"%{search}%"),
                    Video.channel.ilike(f"%{search}%"),
                ),
            )

        if tags:
            # Filter by tags (stored as JSON)
            for tag in tags:
                filters.append(Video.tags.ilike(f"%{tag}%"))

        if filters:
            query = query.where(*filters)

        # Order by created_at desc by default
        query = query.order_by(Video.created_at.desc())

        # Paginate
        paginator = Paginator(page=page, limit=size)
        items, total = await paginator.paginate(db, query)

        # Convert to response format
        video_responses = [VideoResponse.model_validate(item) for item in items]

        # Calculate pages
        pages = (total + size - 1) // size if size > 0 else 0

        return VideoListResponse(
            items=video_responses,
            total=total,
            page=page,
            size=size,
            pages=pages,
        )

    async def get_video(self, db: AsyncSession, video_uuid: str) -> VideoResponse:
        """Get a single video by UUID."""
        result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        return VideoResponse.model_validate(video)

    async def update_video(self, db: AsyncSession, video_uuid: str, update_data: VideoUpdate) -> VideoResponse:
        """Update video metadata."""
        result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)

        # Handle tags serialization
        if "tags" in update_dict and update_dict["tags"] is not None:
            update_dict["tags"] = json.dumps(update_dict["tags"])

        for field, value in update_dict.items():
            setattr(video, field, value)

        await db.commit()
        await db.refresh(video)

        return VideoResponse.model_validate(video)

    async def update_progress(
        self,
        db: AsyncSession,
        video_uuid: str,
        progress_data: VideoProgressUpdate,
    ) -> VideoResponse:
        """Update video watch progress."""
        result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        # Update progress
        video.last_position = progress_data.last_position

        # Calculate completion percentage and round to 1 decimal place
        if video.duration > 0:
            percentage = (progress_data.last_position / video.duration) * 100
            video.completion_percentage = round(min(percentage, 100.0), 1)
        else:
            video.completion_percentage = 0.0

        await db.commit()
        await db.refresh(video)

        return VideoResponse.model_validate(video)

    async def delete_video(self, db: AsyncSession, video_uuid: str) -> None:
        """Delete a video."""
        result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        await db.delete(video)
        await db.commit()

    async def _fetch_video_info(self, url: str) -> dict[str, Any]:
        """Fetch video information using yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    msg = "Could not extract video information"
                    raise ValueError(msg)

                # Extract relevant fields
                # Parse upload_date from YYYYMMDD format to datetime
                upload_date_str = info.get("upload_date")
                published_at = None
                if upload_date_str and len(upload_date_str) == 8:
                    try:
                        published_at = datetime.strptime(upload_date_str, "%Y%m%d")
                    except ValueError:
                        logger.warning(f"Failed to parse upload date: {upload_date_str}")

                return {
                    "youtube_id": info.get("id", ""),
                    "url": url,
                    "title": info.get("title", "Unknown Title"),
                    "channel": info.get("uploader", "Unknown Channel"),
                    "channel_id": info.get("uploader_id", ""),
                    "duration": int(info.get("duration", 0)),
                    "thumbnail_url": info.get("thumbnail"),
                    "description": info.get("description"),
                    "tags": info.get("tags", []),
                    "published_at": published_at,
                }
        except Exception as e:
            logger.exception(f"Error fetching video info: {e}")
            msg = f"Failed to fetch video information: {e!s}"
            raise ValueError(msg)

    # Phase 2.3: Video Chapter Methods
    async def get_video_chapters(self, db: AsyncSession, video_uuid: str) -> list[VideoChapterResponse]:
        """Get all chapters for a video."""
        # Verify video exists
        video_result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        # Get chapters
        chapters_result = await db.execute(
            select(VideoChapter).where(VideoChapter.video_uuid == video_uuid).order_by(VideoChapter.chapter_number),
        )
        chapters = chapters_result.scalars().all()

        return [VideoChapterResponse.model_validate(chapter) for chapter in chapters]

    async def get_video_chapter(self, db: AsyncSession, video_uuid: str, chapter_id: str) -> VideoChapterResponse:
        """Get a specific chapter for a video."""
        # Verify video exists
        video_result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        # Get chapter
        chapter_result = await db.execute(
            select(VideoChapter).where(
                VideoChapter.id == chapter_id,
                VideoChapter.video_uuid == video_uuid,
            ),
        )
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            msg = f"Chapter {chapter_id} not found"
            raise ValueError(msg)

        return VideoChapterResponse.model_validate(chapter)

    async def update_video_chapter_status(
        self, db: AsyncSession, video_uuid: str, chapter_id: str, status: str,
    ) -> VideoChapterResponse:
        """Update the status of a video chapter."""
        # Verify video exists
        video_result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        # Get chapter
        chapter_result = await db.execute(
            select(VideoChapter).where(
                VideoChapter.id == chapter_id,
                VideoChapter.video_uuid == video_uuid,
            ),
        )
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            msg = f"Chapter {chapter_id} not found"
            raise ValueError(msg)

        # Validate status
        valid_statuses = ["not_started", "in_progress", "done"]
        if status not in valid_statuses:
            msg = f"Invalid status '{status}'. Valid statuses are: {', '.join(valid_statuses)}"
            raise ValueError(msg)

        # Update status
        chapter.status = status
        chapter.updated_at = datetime.now()

        await db.commit()
        await db.refresh(chapter)

        return VideoChapterResponse.model_validate(chapter)

    async def extract_and_create_video_chapters(self, db: AsyncSession, video_uuid: str) -> list[VideoChapterResponse]:
        """Extract chapters from YouTube video and create chapter records."""
        # Get video
        video_result = await db.execute(select(Video).where(Video.uuid == video_uuid))
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with UUID {video_uuid} not found"
            raise ValueError(msg)

        # Extract chapters using yt-dlp
        try:
            chapters_info = await self._fetch_video_chapters(video.url)
        except Exception as e:
            logger.exception(f"Failed to extract chapters for video {video_uuid}")
            msg = f"Failed to extract chapters: {e!s}"
            raise ValueError(msg)

        if not chapters_info:
            # Create a single default chapter for the entire video
            chapters_info = [{
                "title": video.title,
                "start_time": 0,
                "end_time": video.duration,
            }]

        # Clear existing chapters
        existing_chapters_result = await db.execute(
            select(VideoChapter).where(VideoChapter.video_uuid == video_uuid),
        )
        existing_chapters = existing_chapters_result.scalars().all()
        for chapter in existing_chapters:
            await db.delete(chapter)

        # Create new chapters
        chapters = []
        for i, chapter_info in enumerate(chapters_info):
            chapter = VideoChapter(
                video_uuid=video.uuid,
                chapter_number=i + 1,
                title=chapter_info.get("title", f"Chapter {i + 1}"),
                start_time=chapter_info.get("start_time"),
                end_time=chapter_info.get("end_time"),
                status="not_started",
            )
            db.add(chapter)
            chapters.append(chapter)

        await db.commit()

        # Refresh chapters to get IDs
        for chapter in chapters:
            await db.refresh(chapter)

        return [VideoChapterResponse.model_validate(chapter) for chapter in chapters]

    async def _fetch_video_chapters(self, url: str) -> list[dict[str, Any]]:
        """Fetch video chapter information using yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                if not info:
                    return []

                # Extract chapters if available
                chapters = info.get("chapters", [])
                if not chapters:
                    return []

                chapter_list = []
                for chapter in chapters:
                    chapter_list.append({
                        "title": chapter.get("title", "Unknown Chapter"),
                        "start_time": int(chapter.get("start_time", 0)),
                        "end_time": int(chapter.get("end_time", 0)),
                    })

                return chapter_list

        except Exception as e:
            logger.exception(f"Error fetching video chapters: {e}")
            return []


# Service instance
video_service = VideoService()
