import json
import logging
import re
from datetime import UTC, datetime
from io import StringIO
from typing import Any
from uuid import UUID

import aiohttp
import webvtt
import yt_dlp
from fastapi import BackgroundTasks
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

# AI imports removed - using facades instead
from src.ai.rag.background_processor import process_video_rag_background as _process_video_rag_background
from src.core.mode_aware_service import ModeAwareService

# UserContext removed - using UUID directly
from src.database.pagination import Paginator
from src.database.session import async_session_maker
from src.tagging.service import TaggingService
from src.videos.models import Video, VideoChapter
from src.videos.schemas import (
    TranscriptSegment,
    VideoChapterResponse,
    VideoCreate,
    VideoListResponse,
    VideoProgressResponse,
    VideoProgressUpdate,
    VideoResponse,
    VideoTranscriptResponse,
    VideoUpdate,
)
from src.videos.services.video_progress_service import VideoProgressService


logger = logging.getLogger(__name__)


def parse_video_id(video_id: str) -> UUID:
    """Convert string UUID to UUID object with validation."""
    from uuid import UUID
    try:
        return UUID(video_id)
    except ValueError as e:
        msg = f"Invalid UUID format: {video_id}"
        raise ValueError(msg) from e


async def _extract_chapters_background(video_id: str, user_id: UUID) -> None:
    """Extract chapters in background after video creation."""
    try:
        async with async_session_maker() as db:
            await video_service.extract_and_create_video_chapters(db, video_id, user_id)
            logger.info(f"Successfully extracted chapters for video {video_id}")
    except Exception as e:
        logger.exception(f"Failed to extract chapters for video {video_id}: {e}")
        # Don't fail the video creation if chapter extraction fails


async def _extract_video_transcript(video_url: str) -> str | None:
    """Extract transcript from YouTube video using yt-dlp."""
    try:
        # Updated options for cleaner subtitles - using SRT format
        ydl_opts = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitlesformat": "srt",  # Use SRT format to avoid VTT redundancy issues
            "subtitleslangs": ["en"],
            "skip_download": True,
            "quiet": True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Get video info with subtitles
            info = ydl.extract_info(video_url, download=False)

            # Try to get subtitles
            subtitles = info.get("subtitles", {})
            automatic_captions = info.get("automatic_captions", {})

            # Prefer manual subtitles over automatic ones
            subs_to_use = subtitles.get("en") or automatic_captions.get("en")

            if not subs_to_use:
                return None

            # Find the best subtitle format (prefer SRT to avoid VTT issues)
            subtitle_url = None
            for sub in subs_to_use:
                if sub.get("ext") == "srt":
                    subtitle_url = sub.get("url")
                    break

            # Fallback to any available subtitle
            if not subtitle_url and subs_to_use:
                subtitle_url = subs_to_use[0].get("url")

            if not subtitle_url:
                return None

            # Download and parse subtitle content
            async with aiohttp.ClientSession() as session, session.get(subtitle_url) as response:
                if response.status == 200:
                    content = await response.text()
                    # Simple SRT parser - extract text lines
                    lines = content.split("\n")
                    transcript_lines = []

                    for line_text in lines:
                        line = line_text.strip()
                        # Skip timestamp lines and sequence numbers
                        if not line or "-->" in line or line.isdigit():
                            continue
                        transcript_lines.append(line)

                    return " ".join(transcript_lines)

    except Exception as e:
        logger.exception(f"Failed to extract transcript for {video_url}: {e}")
        return None

    return None


class VideoService(ModeAwareService):
    """Service for managing videos."""

    def __init__(self) -> None:
        """Initialize the video service."""
        super().__init__()

    def _video_to_dict(self, video: Video) -> dict[str, Any]:
        """Convert Video SQLAlchemy object to dict to avoid lazy loading issues."""
        return {
            "id": video.id,
            "uuid": video.id,  # Map id to uuid for schema compatibility
            "youtube_id": video.youtube_id,
            "url": video.url,
            "title": video.title,
            "channel": video.channel,
            "channel_id": video.channel_id,
            "duration": video.duration,
            "thumbnail_url": video.thumbnail_url,
            "description": video.description,
            "tags": video.tags,
            "transcript": video.transcript,
            "transcript_data": video.transcript_data,
            "archived": video.archived,
            "archived_at": video.archived_at,
            "published_at": video.published_at,
            "created_at": video.created_at,
            "updated_at": video.updated_at,
        }

    async def create_video(
        self, db: AsyncSession, video_data: VideoCreate, background_tasks: BackgroundTasks, user_id: UUID
    ) -> VideoResponse:
        """Create a new video by fetching metadata from YouTube."""
        # Log the access
        self.log_access("create", user_id, "video")

        # Get the user ID for creation
        query_builder = self.get_query_builder(Video)
        user_id_for_creation = query_builder.apply_user_filter_for_creation(user_id)

        # Extract video info using yt-dlp
        video_info = await self.fetch_video_info(video_data.url)

        # Check if video already exists for this user
        existing_query = select(Video).where(Video.youtube_id == video_info["youtube_id"])
        existing_filtered_query = query_builder.apply_user_filter(existing_query, user_id)
        existing = await db.execute(existing_filtered_query)
        existing_video = existing.scalar_one_or_none()
        if existing_video:
            # Return existing video with flag indicating it already existed
            video_dict = self._video_to_dict(existing_video)
            video_dict["already_exists"] = True
            return VideoResponse.model_validate(video_dict)

        # Extract transcript immediately (simple approach)
        transcript_content = await _extract_video_transcript(video_data.url)

        # Create video record
        video = Video(
            user_id=user_id_for_creation,
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
            transcript=transcript_content,
        )

        db.add(video)
        try:
            await db.commit()
            await db.refresh(video)
        except IntegrityError:
            # Handle race condition - video was created by another request between check and insert
            await db.rollback()
            # Fetch the existing video that was just created
            existing = await db.execute(
                select(Video).where(Video.youtube_id == video_info["youtube_id"]),
            )
            existing_video = existing.scalar_one_or_none()
            if existing_video:
                video_dict = self._video_to_dict(existing_video)
                video_dict["already_exists"] = True
                return VideoResponse.model_validate(video_dict)
            # If we still can't find it, something else is wrong
            raise

        # Trigger automatic tagging
        try:
            tagging_service = TaggingService(db)

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
                content_id=video.id,
                content_type="video",
                user_id=user_id,  # Pass the user_id for personalized tags
                title=video.title,
                content_preview="\n\n".join(content_preview),
            )

            # Update video's tags field with both YouTube and generated tags
            if tags:
                existing_tags = video_info.get("tags", [])
                all_tags = list(set(existing_tags + tags))  # Combine and deduplicate
                video.tags = json.dumps(all_tags)
                await db.commit()

            logger.info(f"Successfully tagged video {video.id} with tags: {tags}")

        except Exception as e:
            # Don't fail video creation if tagging fails
            logger.exception(f"Failed to tag video {video.id}: {e}")

        # Ensure video object is refreshed before validation
        await db.refresh(video)

        # Trigger background RAG processing
        background_tasks.add_task(_process_video_rag_background, video.id)

        # Trigger background chapter extraction
        background_tasks.add_task(_extract_chapters_background, str(video.id), user_id)

        # Convert to dict first to avoid SQLAlchemy lazy loading issues
        return VideoResponse.model_validate(self._video_to_dict(video))

    async def get_videos(
        self,
        db: AsyncSession,
        user_id: UUID,
        page: int = 1,
        size: int = 20,
        channel: str | None = None,
        search: str | None = None,
        tags: list[str] | None = None,
    ) -> VideoListResponse:
        """Get paginated list of videos with optional filtering."""
        # Log the access
        self.log_access("list", user_id, "video")

        # Apply user filtering first
        query_builder = self.get_query_builder(Video)
        base_query = select(Video)
        query = query_builder.apply_user_filter(base_query, user_id)

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
            filters.extend(Video.tags.ilike(f"%{tag}%") for tag in tags)

        if filters:
            query = query.where(*filters)

        # Order by created_at desc by default
        query = query.order_by(Video.created_at.desc())

        # Paginate
        paginator = Paginator(page=page, limit=size)
        items, total = await paginator.paginate(db, query)

        # Convert to response format
        video_responses = [VideoResponse.model_validate(self._video_to_dict(item)) for item in items]

        # Calculate pages
        pages = (total + size - 1) // size if size > 0 else 0

        return VideoListResponse(
            items=video_responses,
            total=total,
            page=page,
            pages=pages,
        )

    async def get_video(self, db: AsyncSession, video_id: str, user_id: UUID) -> VideoResponse:
        """Get a single video by UUID."""
        # Log the access
        self.log_access("get", user_id, "video", video_id)

        # Convert string UUID to UUID object
        video_id_obj = parse_video_id(video_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        return VideoResponse.model_validate(self._video_to_dict(video))

    async def update_video(self, db: AsyncSession, video_id: str, update_data: VideoUpdate, user_id: UUID) -> VideoResponse:
        """Update video metadata."""
        # Log the access
        self.log_access("update", user_id, "video", video_id)

        # Convert string UUID to UUID object
        video_id_obj = parse_video_id(video_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            msg = f"Video with ID {video_id} not found"
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

        return VideoResponse.model_validate(self._video_to_dict(video))

    async def update_progress(
        self,
        db: AsyncSession,
        video_id: str,
        progress_data: VideoProgressUpdate,
        user_id: UUID,
    ) -> VideoProgressResponse:
        """Update video watch progress for a specific user."""
        # UserContext removed - using UUID directly
        progress_service = VideoProgressService(db, user_id)

        return await progress_service.update_video_progress(video_id, progress_data)

    async def get_video_progress(
        self,
        db: AsyncSession,
        video_id: str,
        user_id: UUID,
    ) -> VideoProgressResponse | None:
        """Get video progress for a specific user."""
        # UserContext removed - using UUID directly
        progress_service = VideoProgressService(db, user_id)

        return await progress_service.get_video_progress(video_id)

    async def delete_video(self, db: AsyncSession, video_id: str, user_id: UUID) -> None:
        """Delete a video."""
        # Log the access
        self.log_access("delete", user_id, "video", video_id)

        # Convert string UUID to UUID object
        video_id_obj = parse_video_id(video_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        result = await db.execute(filtered_query)
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        await db.delete(video)
        await db.commit()

    async def fetch_video_info(self, url: str) -> dict[str, Any]:
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
                        published_at = datetime.strptime(upload_date_str, "%Y%m%d").replace(tzinfo=UTC)
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
            raise ValueError(msg) from e

    async def get_video_chapters(self, db: AsyncSession, video_id: str, user_id: UUID) -> list[VideoChapterResponse]:
        """Get all chapters for a video."""
        # Convert string UUID to UUID object
        video_id_obj = parse_video_id(video_id)

        # Debug logging
        logger.info(f"Getting chapters for video {video_id} (UUID: {video_id_obj}) for user {user_id}")

        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        video_result = await db.execute(filtered_query)
        video = video_result.scalar_one_or_none()

        if not video:
            # Check if video exists without user filter
            unfiltered_result = await db.execute(select(Video).where(Video.id == video_id_obj))
            unfiltered_video = unfiltered_result.scalar_one_or_none()
            if unfiltered_video:
                logger.error(f"Video {video_id} exists but belongs to user {unfiltered_video.user_id}, not {user_id}")
            else:
                logger.error(f"Video {video_id} not found in database at all")
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            logger.error(f"User {user_id} does not own video {video_id} (owned by {video.user_id})")
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Get chapters
        chapters_result = await db.execute(
            select(VideoChapter).where(VideoChapter.video_id == video_id_obj).order_by(VideoChapter.chapter_number),
        )
        chapters = chapters_result.scalars().all()

        # Return empty list if no chapters found - frontend will fall back to description extraction
        return [VideoChapterResponse.model_validate(chapter) for chapter in chapters]

    async def get_video_chapter(self, db: AsyncSession, video_id: str, chapter_id: str, user_id: UUID) -> VideoChapterResponse:
        """Get a specific chapter for a video."""
        # Convert string UUID to UUID object
        video_id_obj = parse_video_id(video_id)

        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id_obj)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        video_result = await db.execute(filtered_query)
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Get chapter
        chapter_result = await db.execute(
            select(VideoChapter).where(
                VideoChapter.id == chapter_id,
                VideoChapter.video_id == video_id,
            ),
        )
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            msg = f"Chapter {chapter_id} not found"
            raise ValueError(msg)

        return VideoChapterResponse.model_validate(chapter)

    async def update_video_chapter_status(
        self,
        db: AsyncSession,
        video_id: str,
        chapter_id: str,
        status: str,
        user_id: UUID,
    ) -> VideoChapterResponse:
        """Update the status of a video chapter."""
        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        video_result = await db.execute(filtered_query)
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Get chapter
        chapter_result = await db.execute(
            select(VideoChapter).where(
                VideoChapter.id == chapter_id,
                VideoChapter.video_id == video_id,
            ),
        )
        chapter = chapter_result.scalar_one_or_none()

        if not chapter:
            msg = f"Chapter {chapter_id} not found"
            raise ValueError(msg)

        # Validate status
        valid_statuses = ["not_started", "in_progress", "completed"]
        if status not in valid_statuses:
            msg = f"Invalid status '{status}'. Valid statuses are: {', '.join(valid_statuses)}"
            raise ValueError(msg)

        # Update status
        chapter.status = status
        chapter.updated_at = datetime.now(UTC)

        # Recalculate video completion percentage based on all chapters
        all_chapters_result = await db.execute(
            select(VideoChapter).where(VideoChapter.video_id == video_id),
        )
        all_chapters = all_chapters_result.scalars().all()

        if all_chapters:
            # Update video timestamp (chapter completion is tracked per-user in VideoProgress)
            video.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(chapter)

        return VideoChapterResponse.model_validate(chapter)

    async def sync_chapter_progress(
        self,
        db: AsyncSession,
        video_id: str,
        completed_chapter_ids: list[str],
        total_chapters: int,
        user_id: UUID | None = None,
    ) -> VideoResponse:
        """Sync chapter progress from web app and update video completion percentage."""
        # Verify video exists
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Calculate completion percentage from chapter progress
        completed_count = len(completed_chapter_ids)
        completion_percentage = (completed_count / total_chapters) * 100

        # Update or create VideoProgress record if user_id is provided
        if user_id:
            from src.videos.models import VideoProgress

            # Find or create progress record
            progress_query = select(VideoProgress).where(
                VideoProgress.video_id == video_id,
                VideoProgress.user_id == user_id,
            )
            progress_result = await db.execute(progress_query)
            progress = progress_result.scalar_one_or_none()

            if not progress:
                progress = VideoProgress(
                    video_id=video_id,
                    user_id=user_id,
                )
                db.add(progress)

            # Update completion percentage
            progress.completion_percentage = completion_percentage
            progress.last_watched_at = datetime.now(UTC)
            progress.updated_at = datetime.now(UTC)

        # Update video timestamp
        video.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(video)

        return VideoResponse.model_validate(self._video_to_dict(video))

    async def extract_and_create_video_chapters(self, db: AsyncSession, video_id: str, user_id: UUID) -> list[VideoChapterResponse]:
        """Extract chapters from YouTube video and create chapter records."""
        # Apply user filtering
        query_builder = self.get_query_builder(Video)
        base_query = select(Video).where(Video.id == video_id)
        filtered_query = query_builder.apply_user_filter(base_query, user_id)

        video_result = await db.execute(filtered_query)
        video = video_result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Validate user ownership
        if not query_builder.validate_user_ownership(video, user_id):
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        # Extract chapters using yt-dlp
        try:
            chapters_info = await self._fetch_video_chapters(video.url)
        except Exception as e:
            logger.exception(f"Failed to extract chapters for video {video_id}")
            msg = f"Failed to extract chapters: {e!s}"
            raise ValueError(msg) from e

        if not chapters_info:
            # Create a single default chapter for the entire video
            chapters_info = [
                {
                    "title": video.title,
                    "start_time": 0,
                    "end_time": video.duration,
                },
            ]

        # Clear existing chapters
        existing_chapters_result = await db.execute(
            select(VideoChapter).where(VideoChapter.video_id == video_id),
        )
        existing_chapters = existing_chapters_result.scalars().all()
        for chapter in existing_chapters:
            await db.delete(chapter)

        # Create new chapters
        chapters = []
        for i, chapter_info in enumerate(chapters_info):
            chapter = VideoChapter(
                video_id=video.id,  # This is correct - VideoChapter uses video_id
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

    async def get_video_transcript_segments(self, db: AsyncSession, video_id: str) -> VideoTranscriptResponse:
        """Get transcript segments with timestamps for a video."""
        # Get video to ensure it exists
        result = await db.execute(
            select(Video).where(Video.id == video_id),
        )
        video = result.scalar_one_or_none()

        if not video:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        try:
            # Use JSONB data if available (fast path)
            if video.transcript_data and video.transcript_data.get("segments"):
                segments = [
                    TranscriptSegment(
                        start_time=seg["start"],
                        end_time=seg["end"],
                        text=seg["text"]
                    )
                    for seg in video.transcript_data["segments"]
                ]
                return VideoTranscriptResponse(
                    video_id=video.id,
                    segments=segments,
                    total_segments=video.transcript_data.get("total_segments", len(segments)),
                )

            # Fallback: extract segments from video URL (backward compatibility)
            logger.info(f"No JSONB data found for video {video_id}, extracting segments from URL")
            segments = await self._extract_video_transcript_segments(video.url)
            return VideoTranscriptResponse(
                video_id=video.id,
                segments=segments,
                total_segments=len(segments),
            )
        except Exception as e:
            logger.exception(f"Failed to get transcript segments for video {video_id}")
            msg = f"Failed to get transcript segments: {e!s}"
            raise ValueError(msg) from e

    async def _extract_video_transcript_segments(self, video_url: str) -> list[TranscriptSegment]:
        """Extract transcript segments with timestamps from YouTube video using yt-dlp."""
        try:
            # Updated options for cleaner subtitles - using SRT format
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitlesformat": "srt",  # Use SRT format to avoid VTT redundancy issues
                "subtitleslangs": ["en"],
                "skip_download": True,
                "quiet": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Get video info with subtitles
                info = ydl.extract_info(video_url, download=False)

                # Try to get subtitles
                subtitles = info.get("subtitles", {})
                automatic_captions = info.get("automatic_captions", {})

                # Prefer manual subtitles over automatic ones
                subs_to_use = subtitles.get("en") or automatic_captions.get("en")

                if not subs_to_use:
                    return []

                # Find the best subtitle format (prefer SRT to avoid VTT issues)
                subtitle_url = None
                for sub in subs_to_use:
                    if sub.get("ext") == "srt":
                        subtitle_url = sub.get("url")
                        break

                # Fallback to any available subtitle
                if not subtitle_url and subs_to_use:
                    subtitle_url = subs_to_use[0].get("url")

                if not subtitle_url:
                    return []

                # Download and parse subtitle content
                async with aiohttp.ClientSession() as session, session.get(subtitle_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        return self._parse_srt_segments(content)

        except Exception as e:
            logger.exception(f"Failed to extract transcript segments for {video_url}: {e}")
            return []

        return []

    def _parse_vtt_segments(self, vtt_content: str) -> list[TranscriptSegment]:
        """Parse VTT content to extract transcript segments with timestamps."""
        return [
            TranscriptSegment(start_time=caption.start_in_seconds, end_time=caption.end_in_seconds, text=caption.text)
            for caption in webvtt.read_buffer(StringIO(vtt_content))
        ]

    def _parse_srt_segments(self, srt_content: str) -> list[TranscriptSegment]:
        """Parse SRT content to extract transcript segments with timestamps."""
        segments = []
        # Split into subtitle blocks
        blocks = re.split(r"\n\n+", srt_content.strip())

        for block in blocks:
            lines = block.strip().split("\n")
            if len(lines) >= 3 and "-->" in lines[1]:
                # Parse timestamp line
                timestamp_match = re.match(r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})", lines[1])
                if timestamp_match:
                    start_str, end_str = timestamp_match.groups()

                    # Convert timestamp to seconds
                    def timestamp_to_seconds(ts: str) -> float:
                        h, m, s = ts.replace(",", ".").split(":")
                        return float(h) * 3600 + float(m) * 60 + float(s)

                    start_time = timestamp_to_seconds(start_str)
                    end_time = timestamp_to_seconds(end_str)

                    # Join remaining lines as text
                    text = " ".join(lines[2:])

                    segments.append(TranscriptSegment(start_time=start_time, end_time=end_time, text=text))

        return segments

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

                return [
                    {
                        "title": chapter.get("title", "Unknown Chapter"),
                        "start_time": int(chapter.get("start_time", 0)),
                        "end_time": int(chapter.get("end_time", 0)),
                    }
                    for chapter in chapters
                ]

        except Exception as e:
            logger.exception(f"Error fetching video chapters: {e}")
            return []

    async def get_video_progress_percentage(self, video_id: UUID, user_id: UUID | None = None) -> int:
        """Calculate video progress based on user's watch progress.

        Returns percentage (0-100) based on time-based progress from VideoProgress records.
        This matches the ProgressCalculator interface and provides time-based progress.
        """
        from src.videos.models import VideoProgress

        # Use async session from session maker
        async with async_session_maker() as session:
            # Get the video to get total duration
            video_query = select(Video).where(Video.id == video_id)
            video_result = await session.execute(video_query)
            video = video_result.scalar_one_or_none()

            if not video or not video.duration:
                return 0

            # If no user_id provided, try to use default user
            if user_id is None:
                from src.config.settings import get_settings
                settings = get_settings()

                # In single-user mode, use default user; in multi-user mode, return 0
                if settings.AUTH_PROVIDER == "none":
                    from src.auth.manager import NoAuthProvider
                    user_id = NoAuthProvider.DEFAULT_USER_ID
                else:
                    # Multi-user mode - we can't determine user without context
                    return 0

            # Get progress record for time-based calculation
            progress_query = select(VideoProgress).where(
                VideoProgress.video_id == video_id,
                VideoProgress.user_id == user_id
            )
            progress_result = await session.execute(progress_query)
            progress = progress_result.scalar_one_or_none()

            if not progress or progress.last_position is None:
                return 0

            # Calculate time-based progress percentage
            progress_percentage = min(100, (progress.last_position / video.duration) * 100)
            return int(progress_percentage)

    async def get_chapter_completion_stats(self, video_id: UUID) -> dict:
        """Get detailed chapter completion statistics.

        Returns statistics about chapter completion for the video.
        """
        from sqlalchemy import func

        # Use async session from session maker
        async with async_session_maker() as session:
            # Count total and completed chapters
            stats_query = select(
                func.count(VideoChapter.id).label("total"),
                func.count(VideoChapter.id).filter(VideoChapter.status == "completed").label("completed"),
                func.count(VideoChapter.id).filter(VideoChapter.status == "in_progress").label("in_progress"),
            ).where(VideoChapter.video_id == video_id)

            result = await session.execute(stats_query)
            stats = result.first()

            if not stats or stats.total == 0:
                # No chapters available, return default stats
                return {
                    "total_chapters": 0,
                    "completed_chapters": 0,
                    "in_progress_chapters": 0,
                    "not_started_chapters": 0,
                    "completion_percentage": 0,
                    "uses_video_based_progress": True,
                }

            completed_chapters = stats.completed
            in_progress_chapters = stats.in_progress
            not_started_chapters = stats.total - completed_chapters - in_progress_chapters

            return {
                "total_chapters": stats.total,
                "completed_chapters": completed_chapters,
                "in_progress_chapters": in_progress_chapters,
                "not_started_chapters": not_started_chapters,
                "completion_percentage": int((completed_chapters / stats.total) * 100) if stats.total > 0 else 0,
                "uses_video_based_progress": False,
            }


# Service instance
video_service = VideoService()
