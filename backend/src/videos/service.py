import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import aiohttp
import yt_dlp
from fastapi import BackgroundTasks
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.rag.service import RAGService
from src.database.pagination import Paginator
from src.database.session import async_session_maker
from src.tagging.service import TaggingService
from src.videos.models import Video, VideoChapter
from src.videos.schemas import (
    TranscriptSegment,
    VideoChapterResponse,
    VideoCreate,
    VideoListResponse,
    VideoResponse,
    VideoTranscriptResponse,
    VideoUpdate,
)


logger = logging.getLogger(__name__)


def parse_video_id(video_id: str) -> UUID:
    """Convert string UUID to UUID object with validation."""
    from uuid import UUID

    try:
        return UUID(video_id)
    except ValueError as e:
        msg = f"Invalid UUID format: {video_id}"
        raise ValueError(msg) from e


def _create_downloader(options: dict[str, Any]) -> yt_dlp.YoutubeDL:
    """Return a YoutubeDL instance without strict typing complaints."""
    return yt_dlp.YoutubeDL(options)  # type: ignore[arg-type]


async def _embed_video_background(video_id: str) -> None:
    """Background task to embed a video."""
    try:
        async with async_session_maker() as session:
            await RAGService().process_video(session, parse_video_id(video_id))
    except Exception:
        logger.exception("Failed to embed video %s", video_id)


async def _mark_video_status(video_id: str, status: str, error_context: str = "") -> None:
    """Mark video chapter extraction status."""
    try:
        async with async_session_maker() as db:
            video_result = await db.execute(select(Video).where(Video.id == video_id))
            video = video_result.scalar_one_or_none()
            if video:
                video.chapters_status = status
                video.chapters_extracted_at = datetime.now(UTC)
                await db.commit()
    except Exception as update_error:
        logger.warning(f"Failed to mark video {video_id} as {status}{error_context}: {update_error}")


async def _handle_video_not_found_error(
    video_id: str, attempt: int, max_retries: int, retry_delay: int, e: ValueError
) -> bool:
    """Handle video not found error. Returns True if should retry, False if should stop."""
    if attempt < max_retries - 1:
        logger.warning(f"Video {video_id} not found on attempt {attempt + 1}, retrying in {retry_delay}s...")
        await asyncio.sleep(retry_delay)
        return True

    logger.exception(f"Video {video_id} not found after {max_retries} attempts: {e}")
    await _mark_video_status(video_id, "failed")
    return False


async def _try_extract_chapters(video_id: str, user_id: UUID) -> bool:
    """Try to extract chapters. Returns True if successful, False if failed."""
    async with async_session_maker() as db:
        # Mark as processing
        video_result = await db.execute(select(Video).where(Video.id == video_id))
        video = video_result.scalar_one_or_none()
        if video:
            video.chapters_status = "processing"
            await db.commit()

        chapters = await video_service.extract_and_create_video_chapters(db, video_id, user_id)
        logger.info(f"Successfully extracted {len(chapters)} chapters for video {video_id}")
        return True


async def _extract_chapters_background(video_id: str, user_id: UUID) -> None:
    """Extract chapters in background after video creation with retry logic."""
    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        try:
            if await _try_extract_chapters(video_id, user_id):
                return
        except ValueError as e:
            if "not found" in str(e).lower():
                if await _handle_video_not_found_error(video_id, attempt, max_retries, retry_delay, e):
                    continue
                return

            logger.exception(f"Failed to extract chapters for video {video_id} on attempt {attempt + 1}: {e}")
            await _mark_video_status(video_id, "failed", " after ValueError")
            return
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(
                    f"Chapter extraction failed for video {video_id} on attempt {attempt + 1}, retrying in {retry_delay}s: {e}"
                )
                await asyncio.sleep(retry_delay)
                continue

            logger.exception(f"Failed to extract chapters for video {video_id} after {max_retries} attempts: {e}")
            await _mark_video_status(video_id, "failed", " after final attempt")
            return


async def _process_transcript_to_jsonb(video_id: UUID) -> None:
    """Process transcript text into JSONB segments in background."""
    try:
        async with async_session_maker() as db:
            result = await db.execute(select(Video).where(Video.id == video_id))
            video = result.scalar_one_or_none()

            if not video or not video.transcript:
                return

            # Check if already processed
            if video.transcript_data and video.transcript_data.get("segments"):
                logger.info(f"Video {video_id} already has transcript segments")
                return

            logger.info(f"Processing transcript segments for video {video_id}")

            # Extract segments with timestamps
            segments = await video_service.extract_video_transcript_segments(video.url)

            if segments:
                # Store segments in JSONB
                video.transcript_data = {
                    "segments": [{"start": seg.start_time, "end": seg.end_time, "text": seg.text} for seg in segments],
                    "total_segments": len(segments),
                    "processed_at": datetime.now(UTC).isoformat(),
                }
                await db.commit()
                logger.info(f"Stored {len(segments)} transcript segments for video {video_id}")

    except Exception as e:
        logger.exception(f"Failed to process transcript segments for video {video_id}: {e}")


async def _extract_video_transcript(video_url: str) -> str | None:
    """Extract transcript from YouTube video using yt-dlp."""
    try:
        # Metadata-only options to avoid triggering any downloads or format selection
        ydl_opts: dict[str, Any] = {
            "skip_download": True,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "ignore_no_formats_error": True,
            "allow_unplayable_formats": True,
        }

        with _create_downloader(ydl_opts) as ydl:
            # Get video info with subtitles (avoid format selection)
            info = ydl.extract_info(video_url, download=False, process=False)

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


class VideoService:
    """Service for managing videos."""

    def __init__(self) -> None:
        """Initialize the video service."""

    async def _get_user_video(self, db: AsyncSession, video_id: str, user_id: UUID) -> Video:
        """Get video with optimized user ownership validation."""
        video_id_obj = parse_video_id(video_id)

        # Single query with user filter
        result = await db.execute(select(Video).where(Video.id == video_id_obj, Video.user_id == user_id))
        video = result.scalar_one_or_none()

        if not video:
            # Generic error message to avoid exposing ownership info
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        return video

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
            "chapters_status": video.chapters_status,
            "chapters_extracted_at": video.chapters_extracted_at,
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
        # Get the user ID for creation
        user_id_for_creation = user_id

        # Extract video info using yt-dlp
        video_info = await self.fetch_video_info(video_data.url)

        # Check if video already exists for this user
        existing = await db.execute(
            select(Video).where(Video.youtube_id == video_info["youtube_id"], Video.user_id == user_id)
        )
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
            from src.tagging.processors.video_processor import process_video_for_tagging

            tagging_service = TaggingService(db)
            content_data = await process_video_for_tagging(video.id, db)
            if not content_data:
                logger.warning("Skipping tagging for missing video %s", video.id)
            else:
                tags = await tagging_service.tag_content(
                    content_id=video.id,
                    content_type="video",
                    user_id=user_id,
                    title=content_data.get("title", ""),
                    content_preview=content_data.get("content_preview", ""),
                )

                # Update video's tags field with both YouTube and generated tags
                if tags:
                    existing_tags = video_info.get("tags", [])
                    all_tags = list(set(existing_tags + tags))  # Combine and deduplicate
                    video.tags = json.dumps(all_tags)
                    await db.commit()

                logger.info("Successfully tagged video %s with tags: %s", video.id, tags)

        except Exception as e:
            # Don't fail video creation if tagging fails
            logger.exception("Failed to tag video %s: %s", video.id, e)

        # Ensure video object is refreshed before validation
        await db.refresh(video)

        # Trigger background RAG processing of transcript when available
        background_tasks.add_task(_embed_video_background, str(video.id))

        # Trigger background chapter extraction
        background_tasks.add_task(_extract_chapters_background, str(video.id), user_id)

        # Trigger background transcript segment processing
        if video.transcript:  # Only if we have transcript text
            background_tasks.add_task(_process_transcript_to_jsonb, video.id)

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
        # Apply user filtering first
        query = select(Video).where(Video.user_id == user_id)

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
        # Get video with user validation (optimized single query)
        video = await self._get_user_video(db, video_id, user_id)

        return VideoResponse.model_validate(self._video_to_dict(video))

    async def update_video(
        self, db: AsyncSession, video_id: str, update_data: VideoUpdate, user_id: UUID
    ) -> VideoResponse:
        """Update video metadata."""
        # Get video with user validation (optimized single query)
        video = await self._get_user_video(db, video_id, user_id)

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

    async def fetch_video_info(self, url: str) -> dict[str, Any]:
        """Fetch video information using yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            # Do not force format selection when only extracting metadata
            # This avoids yt_dlp raising "Requested format is not available"
            # for region/permission-restricted variants.
            "noplaylist": True,
            "ignoreerrors": True,  # Continue on download errors
            "ignore_no_formats_error": True,
            "allow_unplayable_formats": True,
        }

        try:
            with _create_downloader(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False, process=False)

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
                    "duration": int(info.get("duration") or 0),
                    "thumbnail_url": info.get("thumbnail"),
                    "description": info.get("description"),
                    "tags": info.get("tags", []),
                    "published_at": published_at,
                }
        except Exception as e:
            logger.exception(f"Error fetching video info: {e}")
            # Return minimal info instead of failing completely
            # Extract video ID from URL
            video_id = ""
            if "youtube.com/watch?v=" in url:
                video_id = url.split("v=")[1].split("&")[0]
            elif "youtu.be/" in url:
                video_id = url.split("youtu.be/")[1].split("?")[0]

            # Return minimal required info
            return {
                "youtube_id": video_id or "unknown",
                "url": url,
                "title": "Video (info extraction failed)",
                "channel": "Unknown Channel",
                # Use non-empty placeholder and non-zero duration to satisfy schema
                "channel_id": "unknown",
                "duration": 1,
                "thumbnail_url": None,
                "description": f"Failed to extract video info: {e!s}",
                "tags": [],
                "published_at": None,
            }

    async def get_video_chapters(self, db: AsyncSession, video_id: str, user_id: UUID) -> list[VideoChapterResponse]:
        """Get all chapters for a video."""
        # Get video with user validation (optimized single query)
        video = await self._get_user_video(db, video_id, user_id)

        # Debug logging
        logger.info(f"Getting chapters for video {video_id} (UUID: {video.id}) for user {user_id}")

        # Get chapters
        chapters_result = await db.execute(
            select(VideoChapter).where(VideoChapter.video_id == video.id).order_by(VideoChapter.chapter_number),
        )
        chapters = chapters_result.scalars().all()

        # If no chapters found and extraction hasn't been attempted, try to extract automatically
        if not chapters and video.chapters_status == "pending":
            logger.info(
                f"No chapters found for video {video_id} and status is pending, attempting automatic extraction as fallback"
            )
            try:
                chapters = await self.extract_and_create_video_chapters(db, video_id, user_id)
                logger.info(f"Successfully extracted {len(chapters)} chapters as fallback for video {video_id}")
                return chapters
            except Exception as e:
                logger.warning(f"Fallback chapter extraction failed for video {video_id}: {e}")
                # Mark as failed so we don't keep retrying
                video.chapters_status = "failed"
                video.chapters_extracted_at = datetime.now(UTC)
                await db.commit()
                # Return empty list - frontend will fall back to description extraction
                return []

        # Return existing chapters
        return [VideoChapterResponse.model_validate(chapter) for chapter in chapters]

    async def get_video_chapter(
        self, db: AsyncSession, video_id: str, chapter_id: str, user_id: UUID
    ) -> VideoChapterResponse:
        """Get a specific chapter for a video."""
        # Get video with user validation (optimized single query)
        video = await self._get_user_video(db, video_id, user_id)

        # Get chapter
        chapter_result = await db.execute(
            select(VideoChapter).where(
                VideoChapter.id == chapter_id,
                VideoChapter.video_id == video.id,
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
        # Get video with user validation (optimized single query)
        video = await self._get_user_video(db, video_id, user_id)

        # Get chapter
        chapter_result = await db.execute(
            select(VideoChapter).where(
                VideoChapter.id == chapter_id,
                VideoChapter.video_id == video.id,
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
            select(VideoChapter).where(VideoChapter.video_id == video.id),
        )
        all_chapters = all_chapters_result.scalars().all()

        if all_chapters:
            # Update video timestamp (chapter completion is tracked per-user in unified progress system)
            video.updated_at = datetime.now(UTC)

        # Update unified progress to reflect chapter completion state
        # Compute completion percentage from completed chapters and persist via the unified progress service.
        try:
            if all_chapters:
                completed_chapter_ids = [str(c.id) for c in all_chapters if c.status == "completed"]
                total = len(all_chapters)
                completion_pct = (len(completed_chapter_ids) / total) * 100 if total > 0 else 0.0

                # Persist unified progress for this user/video via facade (imports locally to avoid circular deps)
                from src.videos.facade import videos_facade

                await videos_facade.update_video_progress(
                    video.id,
                    user_id,
                    {"completion_percentage": completion_pct, "completed_chapters": completed_chapter_ids},
                )
        except Exception as e:
            logger.warning(f"Failed to update unified progress for video {video_id} after chapter status change: {e}")

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
        # If user_id is provided, verify ownership; otherwise just get the video
        if user_id:
            video = await self._get_user_video(db, video_id, user_id)
        else:
            # Background tasks without user context
            video_id_obj = parse_video_id(video_id)
            video_result = await db.execute(select(Video).where(Video.id == video_id_obj))
            video = video_result.scalar_one_or_none()
            if not video:
                msg = f"Video with ID {video_id} not found"
                raise ValueError(msg)

        # Calculate completion percentage from chapter progress
        completed_count = len(completed_chapter_ids)
        completion_percentage = (completed_count / total_chapters) * 100

        # Update progress using facade if user_id is provided
        if user_id:
            from src.videos.facade import videos_facade

            progress_data = {
                "completion_percentage": completion_percentage,
                "completed_chapters": completed_chapter_ids,
            }
            await videos_facade.update_video_progress(parse_video_id(video_id), user_id, progress_data)

        # Update video timestamp
        video.updated_at = datetime.now(UTC)

        await db.commit()
        await db.refresh(video)

        return VideoResponse.model_validate(self._video_to_dict(video))

    async def extract_and_create_video_chapters(
        self, db: AsyncSession, video_id: str, user_id: UUID
    ) -> list[VideoChapterResponse]:
        """Extract chapters from YouTube video and create chapter records."""
        # Get video with user validation (optimized single query)
        video = await self._get_user_video(db, video_id, user_id)

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
            select(VideoChapter).where(VideoChapter.video_id == video.id),
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

        # Update video chapter extraction status
        video.chapters_status = "completed"
        video.chapters_extracted_at = datetime.now(UTC)

        await db.commit()

        # Refresh chapters to get IDs
        for chapter in chapters:
            await db.refresh(chapter)

        return [VideoChapterResponse.model_validate(chapter) for chapter in chapters]

    async def get_transcript_info(self, db: AsyncSession, video_id: str) -> dict[str, Any] | None:
        """Get transcript metadata without loading full segments."""
        video_id_obj = parse_video_id(video_id)

        # Only fetch transcript_data field
        result = await db.execute(select(Video.transcript_data).where(Video.id == video_id_obj))
        row = result.first()

        if not row or not row.transcript_data:
            return None

        return {
            "has_transcript": True,
            "segment_count": row.transcript_data.get("total_segments", 0),
            "processed_at": row.transcript_data.get("processed_at"),
        }

    async def search_video(
        self, db: AsyncSession, video_id: str, user_id: UUID, query: str, limit: int = 5
    ) -> list[dict]:
        """Search this video's transcript chunks using pgvector."""
        # Ownership validation
        video = await self._get_user_video(db, video_id, user_id)

        from src.ai.rag.embeddings import VectorRAG

        rag = VectorRAG()
        results = await rag.search(db, doc_type="video", query=query, limit=limit, doc_id=video.id)
        # Convert SearchResult objects to dicts for callers
        return [r.model_dump() for r in results]

    async def get_video_transcript_segments(
        self, db: AsyncSession, video_id: str, user_id: UUID | None = None
    ) -> VideoTranscriptResponse:
        """Get transcript segments with timestamps for a video."""
        # Convert string UUID to UUID object
        video_id_obj = parse_video_id(video_id)

        # Get video to ensure it exists - ONLY load necessary fields
        query = select(Video.id, Video.url, Video.transcript_data).where(Video.id == video_id_obj)
        if user_id:
            query = query.where(Video.user_id == user_id)
        result = await db.execute(query)
        video_data = result.first()

        if not video_data:
            msg = f"Video with ID {video_id} not found"
            raise ValueError(msg)

        try:
            # Use JSONB data if available (fast path)
            if video_data.transcript_data and video_data.transcript_data.get("segments"):
                segments = [
                    TranscriptSegment.model_validate(
                        {"start_time": seg["start"], "end_time": seg["end"], "text": seg["text"]}
                    )
                    for seg in video_data.transcript_data["segments"]
                ]
                response_payload = {
                    "video_id": video_data.id,
                    "segments": segments,
                    "total_segments": video_data.transcript_data.get("total_segments", len(segments)),
                }
                return VideoTranscriptResponse.model_validate(response_payload)

            # Fallback: extract segments from video URL (backward compatibility)
            logger.info(f"No JSONB data found for video {video_id}, extracting segments from URL")
            segments = await self.extract_video_transcript_segments(video_data.url)

            # Store segments in JSONB for next time
            if segments:
                # Need to update the actual video record
                update_result = await db.execute(select(Video).where(Video.id == video_id_obj))
                video = update_result.scalar_one()
                video.transcript_data = {
                    "segments": [{"start": seg.start_time, "end": seg.end_time, "text": seg.text} for seg in segments],
                    "total_segments": len(segments),
                    "processed_at": datetime.now(UTC).isoformat(),
                }
                await db.commit()
                logger.info(f"Stored {len(segments)} transcript segments in JSONB for video {video_id}")

            response_payload = {
                "video_id": video_data.id,
                "segments": segments,
                "total_segments": len(segments),
            }
            return VideoTranscriptResponse.model_validate(response_payload)
        except Exception as e:
            logger.exception(f"Failed to get transcript segments for video {video_id}")
            msg = f"Failed to get transcript segments: {e!s}"
            raise ValueError(msg) from e

    async def extract_video_transcript_segments(self, video_url: str) -> list[TranscriptSegment]:
        """Extract transcript segments with timestamps from YouTube video using yt-dlp."""
        try:
            # Metadata-only options to avoid triggering any downloads or format selection
            ydl_opts = {
                "skip_download": True,
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "ignore_no_formats_error": True,
                "allow_unplayable_formats": True,
            }

            with _create_downloader(ydl_opts) as ydl:
                # Get video info with subtitles (avoid format selection)
                info = ydl.extract_info(video_url, download=False, process=False)

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

                    segment_payload = {"start_time": start_time, "end_time": end_time, "text": text}
                    segments.append(TranscriptSegment.model_validate(segment_payload))

        return segments

    async def _fetch_video_chapters(self, url: str) -> list[dict[str, Any]]:
        """Fetch video chapter information using yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "ignore_no_formats_error": True,
            "allow_unplayable_formats": True,
        }

        try:
            with _create_downloader(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False, process=False)

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


# Service instance
video_service = VideoService()
