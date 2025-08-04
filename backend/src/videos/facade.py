"""Videos Module Facade.

Single entry point for all video-related operations.
Coordinates internal video services and provides stable API for other modules.
"""

import logging
from typing import Any
from uuid import UUID

from src.ai.ai_service import get_ai_service
from src.core.interfaces import ContentFacade

from .service import VideoService
from .services.video_content_service import VideoContentService
from .services.video_progress_tracker import VideoProgressTracker


logger = logging.getLogger(__name__)


class VideosFacade(ContentFacade):
    """
    Single entry point for all video operations.

    Coordinates internal video services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Internal services - not exposed to outside modules
        self._video_service = VideoService()
        self._content_service = VideoContentService()  # New base service
        self._progress_service = VideoProgressTracker()  # Implements ProgressTracker protocol
        self._ai_service = get_ai_service()

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get video with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_video_with_progress(content_id, user_id)

    async def get_video_with_progress(self, video_id: UUID, user_id: UUID) -> dict[str, Any]:
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

    async def create_content(self, content_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new video content.

        Implements ContentFacade interface.
        """
        return await self.create_video(content_data, user_id)

    async def create_video(self, video_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new video entry.

        Handles video creation and coordinates all related operations.
        """
        try:
            # Use the new content service which handles tags, progress, and AI processing
            video = await self._content_service.create_content(video_data, user_id)

            return {"video": video, "success": True}

        except Exception as e:
            logger.exception(f"Error creating video for user {user_id}: {e}")
            return {"error": "Failed to create video", "success": False}

    async def add_youtube_video(
        self, youtube_url: str, user_id: UUID, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Add YouTube video to user's library.

        Handles YouTube URL processing and metadata extraction.
        """
        try:
            # Process YouTube URL and extract metadata
            video_data = await self._video_service.process_youtube_url(
                youtube_url, user_id, additional_metadata=metadata or {}
            )

            if not video_data.get("success"):
                return video_data

            video_id = video_data["video"]["id"]

            # Initialize progress tracking
            await self._progress_service.initialize_progress(
                video_id, user_id, total_duration=video_data["video"].get("duration", 0)
            )

            return video_data

        except Exception as e:
            logger.exception(f"Error adding YouTube video {youtube_url} for user {user_id}: {e}")
            return {"error": "Failed to add YouTube video", "success": False}

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update video watching progress.

        Implements ContentFacade interface.
        """
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

    async def update_playback_settings(self, video_id: UUID, user_id: UUID, settings: dict[str, Any]) -> dict[str, Any]:
        """Update video playback settings (speed, quality, etc.)."""
        try:
            # Update playback settings
            updated_settings = await self._progress_service.update_playback_settings(video_id, user_id, settings)

            return {"settings": updated_settings, "success": True}

        except Exception as e:
            logger.exception(f"Error updating playback settings for video {video_id}: {e}")
            return {"error": "Failed to update settings", "success": False}

    async def delete_content(self, content_id: UUID, user_id: UUID) -> bool:
        """
        Delete video content.

        Implements ContentFacade interface.
        """
        return await self.delete_video(content_id, user_id)

    async def delete_video(self, video_id: UUID, user_id: UUID) -> bool:
        """
        Delete video and all related data.

        Coordinates deletion across all video services.
        """
        try:
            # Use content service which handles cleanup of tags and associated data
            return await self._content_service.delete_content(video_id, user_id)

        except Exception as e:
            logger.exception(f"Error deleting video {video_id}: {e}")
            return False

    async def search_videos(self, query: str, user_id: UUID, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Search user's videos.

        Provides unified search across video content and metadata.
        """
        try:
            results = await self._video_service.search_videos(query, user_id, filters or {})

            return {"results": results, "success": True}

        except Exception as e:
            logger.exception(f"Error searching videos for user {user_id}: {e}")
            return {"error": "Search failed", "success": False}

    async def get_user_videos(self, user_id: UUID, include_progress: bool = True) -> dict[str, Any]:
        """
        Get all videos for user.

        Optionally includes progress information.
        """
        try:
            videos = await self._video_service.get_user_videos(user_id)

            if include_progress:
                # Add progress information to each video
                for video in videos:
                    progress = await self._progress_service.get_progress(video.id, user_id)
                    video.progress = progress

            return {"videos": videos, "success": True}

        except Exception as e:
            logger.exception(f"Error getting videos for user {user_id}: {e}")
            return {"error": "Failed to get videos", "success": False}

    async def get_video_chapters(self, video_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get video chapters/segments if available."""
        try:
            # Get chapters - need to pass db session
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                chapters = await self._video_service.get_video_chapters(session, str(video_id))

            # Add progress information for each chapter
            if chapters:
                progress = await self._progress_service.get_progress(video_id, user_id)
                completed_chapters = progress.get("completed_chapters", [])

                for chapter in chapters:
                    chapter["completed"] = chapter.get("id") in completed_chapters

            return {"chapters": chapters or [], "success": True}

        except Exception as e:
            logger.exception(f"Error getting chapters for video {video_id}: {e}")
            return {"error": "Failed to get chapters", "success": False}

    async def mark_chapter_complete(self, video_id: UUID, user_id: UUID, chapter_id: str) -> dict[str, Any]:
        """Mark a video chapter as completed."""
        try:
            result = await self._progress_service.mark_chapter_complete(video_id, user_id, chapter_id)

            return {"result": result, "success": True}

        except Exception as e:
            logger.exception(f"Error marking chapter complete for video {video_id}: {e}")
            return {"error": "Failed to mark chapter complete", "success": False}

    # AI operations
    async def get_video_transcript(self, video_id: UUID, user_id: UUID, url: str) -> str:
        """Get or generate transcript for a video."""
        try:
            return await self._ai_service.process_content(
                content_type="video", action="transcript", user_id=user_id, video_id=str(video_id), url=url
            )
        except Exception as e:
            logger.exception(f"Error getting transcript for video {video_id}: {e}")
            raise

    async def summarize_video(self, video_id: UUID, user_id: UUID, transcript: str) -> str:
        """Generate a summary of the video."""
        try:
            return await self._ai_service.process_content(
                content_type="video", action="summarize", user_id=user_id, video_id=str(video_id), transcript=transcript
            )
        except Exception as e:
            logger.exception(f"Error summarizing video {video_id}: {e}")
            raise

    async def ask_video_question(
        self, video_id: UUID, user_id: UUID, question: str, timestamp: float | None = None
    ) -> str:
        """Ask a question about the video content."""
        try:
            return await self._ai_service.process_content(
                content_type="video",
                action="question",
                user_id=user_id,
                video_id=str(video_id),
                question=question,
                timestamp=timestamp,
            )
        except Exception as e:
            logger.exception(f"Error answering question for video {video_id}: {e}")
            raise

    async def chat_about_video(
        self, video_id: UUID, user_id: UUID, message: str, history: list[dict[str, Any]] | None = None
    ) -> str:
        """Have a conversation about the video."""
        try:
            return await self._ai_service.process_content(
                content_type="video",
                action="chat",
                user_id=user_id,
                video_id=str(video_id),
                message=message,
                history=history,
            )
        except Exception as e:
            logger.exception(f"Error in video chat for {video_id}: {e}")
            raise

    async def process_video_for_rag(self, video_id: UUID, user_id: UUID, transcript: str) -> dict[str, Any]:
        """Process video transcript for RAG indexing."""
        try:
            return await self._ai_service.process_content(
                content_type="video",
                action="process_rag",
                user_id=user_id,
                video_id=str(video_id),
                transcript=transcript,
            )
        except Exception as e:
            logger.exception(f"Error processing video {video_id} for RAG: {e}")
            raise
