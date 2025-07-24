"""Course progress tracker implementing the ProgressTracker protocol.

This provides a simplified interface for progress tracking that doesn't
depend on UserContext or session management.
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.core.interfaces import ProgressTracker
from src.courses.models import Roadmap
from src.database.session import async_session_maker
from src.progress.models import ProgressUpdate
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


class CourseProgressTracker(ProgressTracker):
    """Simplified progress tracker for courses that implements the ProgressTracker protocol."""

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific course and user."""
        async with async_session_maker() as session:
            # Use unified progress service
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, content_id)

            # Get course to get additional info
            course_query = select(Roadmap).where(Roadmap.id == content_id)
            course_result = await session.execute(course_query)
            course = course_result.scalar_one_or_none()

            if not progress_data:
                return {
                    "completion_percentage": 0,
                    "progress_percentage": 0,  # Add both for compatibility
                    "completed_lessons": [],
                    "current_lesson_id": None,
                    "total_lessons": 0,
                    "last_accessed_at": None
                }

            # Extract metadata
            metadata = progress_data.metadata or {}

            # Get lesson completion stats if needed
            progress_percentage = progress_data.progress_percentage or 0

            # Calculate total lessons from metadata if available
            total_lessons = metadata.get("total_lessons", 0)
            if course and total_lessons == 0:
                # Get actual lesson count from the course structure
                from src.courses.services.lesson_query_service import LessonQueryService
                lesson_service = LessonQueryService(session, user_id)
                try:
                    lessons = await lesson_service.list_lessons(content_id, user_id)
                    total_lessons = len(lessons)
                except Exception as e:
                    logger.warning(f"Failed to get lesson count for course {content_id}: {e}")
                    total_lessons = 0

            return {
                "completion_percentage": progress_percentage,
                "progress_percentage": progress_percentage,  # Add both for compatibility
                "completed_lessons": metadata.get("completed_lessons", []),
                "current_lesson_id": metadata.get("current_lesson_id"),
                "total_lessons": total_lessons,
                "last_accessed_at": progress_data.updated_at,
                "created_at": progress_data.created_at,
                "updated_at": progress_data.updated_at
            }

    async def update_progress(
        self,
        content_id: UUID,
        user_id: UUID,
        progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update progress data for specific course and user."""
        async with async_session_maker() as session:
            # Use unified progress service
            progress_service = ProgressService(session)

            # Get current progress
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            # Prepare metadata
            metadata = current_progress.metadata if current_progress else {}
            completion_percentage = current_progress.progress_percentage if current_progress else 0

            # Update metadata fields
            if "completed_lessons" in progress_data:
                metadata["completed_lessons"] = progress_data["completed_lessons"]

                # Calculate completion percentage based on completed lessons
                from src.courses.services.lesson_query_service import LessonQueryService
                lesson_service = LessonQueryService(session, user_id)
                try:
                    lessons = await lesson_service.list_lessons(content_id, user_id)
                    total_lessons = len(lessons)
                    if total_lessons > 0:
                        completed_count = len(progress_data["completed_lessons"])
                        completion_percentage = (completed_count / total_lessons) * 100
                        metadata["total_lessons"] = total_lessons
                except Exception as e:
                    logger.warning(f"Failed to calculate course progress percentage: {e}")

            if "current_lesson_id" in progress_data:
                metadata["current_lesson_id"] = progress_data["current_lesson_id"]

            if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
                completion_percentage = progress_data["completion_percentage"]

            # Handle lesson status updates
            if "lesson_status" in progress_data:
                lesson_id = progress_data.get("lesson_id")
                status = progress_data["lesson_status"]

                if lesson_id and status == "completed":
                    completed_lessons = metadata.get("completed_lessons", [])
                    if str(lesson_id) not in completed_lessons:
                        completed_lessons.append(str(lesson_id))
                        metadata["completed_lessons"] = completed_lessons

                        # Recalculate percentage
                        total_lessons = metadata.get("total_lessons", 0)
                        if total_lessons > 0:
                            completion_percentage = (len(completed_lessons) / total_lessons) * 100

            # Ensure content_type is set in metadata
            metadata["content_type"] = "course"

            # Update using unified progress service
            progress_update = ProgressUpdate(
                progress_percentage=completion_percentage,
                metadata=metadata
            )

            updated = await progress_service.update_progress(
                user_id, content_id, "course", progress_update
            )

            # Return updated progress in expected format
            return {
                "completion_percentage": updated.progress_percentage,
                "completed_lessons": metadata.get("completed_lessons", []),
                "current_lesson_id": metadata.get("current_lesson_id"),
                "total_lessons": metadata.get("total_lessons", 0),
                "last_accessed_at": updated.updated_at,
                "created_at": updated.created_at,
                "updated_at": updated.updated_at
            }

    async def calculate_completion_percentage(
        self,
        content_id: UUID,
        user_id: UUID
    ) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        progress = await self.get_progress(content_id, user_id)
        return progress.get("completion_percentage", 0.0)

    async def update_lesson_status(
        self,
        course_id: UUID,
        lesson_id: UUID,
        user_id: UUID,
        status: str
    ) -> dict[str, Any]:
        """Update a specific lesson's status and recalculate course progress."""
        # This is a convenience method for updating lesson completion
        if status == "completed":
            return await self.update_progress(
                course_id,
                user_id,
                {
                    "lesson_status": status,
                    "lesson_id": lesson_id
                }
            )
        # For non-completed status, just update current lesson
        return await self.update_progress(
            course_id,
            user_id,
            {
                "current_lesson_id": str(lesson_id)
            }
        )
