"""
Courses Module Facade.

Single entry point for all course/roadmap-related operations.
Coordinates internal course services and provides stable API for other modules.
"""

import logging
from typing import Any
from uuid import UUID

from src.ai.ai_service import get_ai_service
from src.core.interfaces import ContentFacade

from .services.course_content_service import CourseContentService
from .services.course_creation_service import CourseCreationService
from .services.course_management_service import CourseManagementService
from .services.course_orchestrator_service import CourseOrchestratorService
from .services.course_progress_service import CourseProgressService
from .services.course_query_service import CourseQueryService
from .services.course_response_builder import CourseResponseBuilder
from .services.course_service import CourseService
from .services.course_update_service import CourseUpdateService
from .services.lesson_creation_service import LessonCreationService
from .services.lesson_deletion_service import LessonDeletionService
from .services.lesson_query_service import LessonQueryService
from .services.lesson_update_service import LessonUpdateService
from .services.progress_tracking_service import ProgressTrackingService


logger = logging.getLogger(__name__)


class CoursesFacade(ContentFacade):
    """
    Single entry point for all course/roadmap operations.

    Coordinates complex course services, manages course lifecycle,
    and provides stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Internal services - not exposed to outside modules
        self._course_service = CourseService()
        self._content_service = CourseContentService()  # New base service
        self._creation_service = CourseCreationService()
        self._management_service = CourseManagementService()
        self._orchestrator_service = CourseOrchestratorService()
        self._progress_service = CourseProgressService()
        self._query_service = CourseQueryService()
        self._response_builder = CourseResponseBuilder()
        self._update_service = CourseUpdateService()
        self._ai_service = get_ai_service()

        # Lesson services
        self._lesson_creation_service = LessonCreationService()
        self._lesson_deletion_service = LessonDeletionService()
        self._lesson_query_service = LessonQueryService()
        self._lesson_update_service = LessonUpdateService()

        # Progress tracking
        self._progress_tracking_service = ProgressTrackingService()

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get course with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_course_with_progress(content_id, user_id)

    async def get_course_with_progress(self, course_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get complete course information with progress.

        Coordinates multiple services to provide comprehensive course data.
        """
        try:
            # Get core course data
            course = await self._course_service.get_course(course_id)
            if not course:
                return {"error": "Course not found"}

            # Get lessons and progress concurrently
            lessons = await self._lesson_query_service.get_course_lessons(course_id)
            progress = await self._progress_service.get_progress(course_id, user_id)
            overall_progress = await self._progress_tracking_service.calculate_course_progress(course_id, user_id)

            # Build comprehensive response
            return await self._response_builder.build_course_response(
                course=course, lessons=lessons, progress=progress, overall_progress=overall_progress, user_id=user_id
            )

        except Exception as e:
            logger.exception(f"Error getting course {course_id} for user {user_id}: {e}")
            return {"error": "Failed to retrieve course"}

    async def create_content(self, content_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new course content.

        Implements ContentFacade interface.
        """
        return await self.create_course(content_data, user_id)

    async def create_course(self, course_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new course/roadmap.

        Handles course creation through the content service.
        """
        try:
            # Use the new content service which handles tags, progress, and AI processing
            course = await self._content_service.create_content(course_data, user_id)

            return {"course": course, "success": True}

        except Exception as e:
            logger.exception(f"Error creating course for user {user_id}: {e}")
            return {"error": "Failed to create course", "success": False}

    async def generate_ai_course(self, topic: str, preferences: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Generate AI-powered course/roadmap.

        Handles AI course generation through creation service.
        """
        try:
            # Generate course using AI
            generation_result = await self._creation_service.generate_ai_course(topic, preferences, user_id)

            if not generation_result.get("success"):
                return generation_result

            course_id = generation_result["course"]["id"]

            # Initialize progress tracking
            await self._progress_service.initialize_progress(course_id, user_id)

            return generation_result

        except Exception as e:
            logger.exception(f"Error generating AI course for user {user_id}: {e}")
            return {"error": "Failed to generate course", "success": False}

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update course progress.

        Implements ContentFacade interface.
        """
        return await self.update_course_progress(content_id, user_id, progress_data)

    async def update_course_progress(
        self, course_id: UUID, user_id: UUID, progress_data: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Update course progress.

        Handles progress updates and milestone tracking for courses.
        """
        try:
            # Update progress through tracking service ONLY
            # This service already handles all progress updates including unified progress
            updated_progress = await self._progress_tracking_service.update_course_progress(
                course_id, user_id, progress_data
            )

            # REMOVED duplicate call to self._progress_service.update_progress()
            # The progress_tracking_service already handles this

            return {"progress": updated_progress, "success": True}

        except Exception as e:
            logger.exception(f"Error updating progress for course {course_id}: {e}")
            return {"error": "Failed to update progress", "success": False}

    async def delete_content(self, content_id: UUID, user_id: UUID) -> bool:
        """
        Delete course content.

        Implements ContentFacade interface.
        """
        return await self.delete_course(content_id, user_id)

    async def delete_course(self, course_id: UUID, user_id: UUID) -> bool:
        """
        Delete course and all related data.

        Coordinates deletion across all course services.
        """
        try:
            # Use content service which handles cleanup of tags and associated data
            return await self._content_service.delete_content(course_id, user_id)

        except Exception as e:
            logger.exception(f"Error deleting course {course_id}: {e}")
            return False

    async def search_courses(self, query: str, user_id: UUID, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Search user's courses.

        Provides unified search across course content.
        """
        try:
            results = await self._query_service.search_courses(query, user_id, filters or {})

            return {"results": results, "success": True}

        except Exception as e:
            logger.exception(f"Error searching courses for user {user_id}: {e}")
            return {"error": "Search failed", "success": False}

    async def get_user_courses(self, user_id: UUID, include_progress: bool = True) -> dict[str, Any]:
        """
        Get all courses for user.

        Optionally includes progress information.
        """
        try:
            courses = await self._course_service.get_user_courses(user_id)

            if include_progress:
                # Add progress information to each course
                for course in courses:
                    progress = await self._progress_service.get_progress(course.id, user_id)
                    course.progress = progress

            return {"courses": courses, "success": True}

        except Exception as e:
            logger.exception(f"Error getting courses for user {user_id}: {e}")
            return {"error": "Failed to get courses", "success": False}

    # Lesson management
    async def create_lesson(self, course_id: UUID, lesson_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """Create new lesson in course."""
        try:
            lesson = await self._lesson_creation_service.create_lesson(course_id, lesson_data, user_id)

            return {"lesson": lesson, "success": True}

        except Exception as e:
            logger.exception(f"Error creating lesson in course {course_id}: {e}")
            return {"error": "Failed to create lesson", "success": False}

    async def update_lesson(self, lesson_id: UUID, lesson_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """Update existing lesson."""
        try:
            lesson = await self._lesson_update_service.update_lesson(lesson_id, lesson_data, user_id)

            return {"lesson": lesson, "success": True}

        except Exception as e:
            logger.exception(f"Error updating lesson {lesson_id}: {e}")
            return {"error": "Failed to update lesson", "success": False}

    async def delete_lesson(self, lesson_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Delete lesson from course."""
        try:
            success = await self._lesson_deletion_service.delete_lesson(lesson_id, user_id)

            return {"success": success}

        except Exception as e:
            logger.exception(f"Error deleting lesson {lesson_id}: {e}")
            return {"error": "Failed to delete lesson", "success": False}

    async def get_lesson(self, lesson_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get individual lesson with progress."""
        try:
            lesson = await self._lesson_query_service.get_lesson(lesson_id)

            if not lesson:
                return {"error": "Lesson not found"}

            # Get lesson progress
            progress = await self._progress_tracking_service.get_lesson_progress(lesson_id, user_id)

            return {"lesson": lesson, "progress": progress, "success": True}

        except Exception as e:
            logger.exception(f"Error getting lesson {lesson_id}: {e}")
            return {"error": "Failed to get lesson", "success": False}

    async def mark_lesson_complete(self, lesson_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Mark lesson as completed."""
        try:
            result = await self._progress_tracking_service.mark_lesson_complete(lesson_id, user_id)

            return {"result": result, "success": True}

        except Exception as e:
            logger.exception(f"Error marking lesson {lesson_id} complete: {e}")
            return {"error": "Failed to mark lesson complete", "success": False}

    # Course management
    async def update_course(self, course_id: UUID, course_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """Update course information."""
        try:
            course = await self._update_service.update_course(course_id, course_data, user_id)

            return {"course": course, "success": True}

        except Exception as e:
            logger.exception(f"Error updating course {course_id}: {e}")
            return {"error": "Failed to update course", "success": False}

    async def reorder_lessons(self, course_id: UUID, lesson_order: list[UUID], user_id: UUID) -> dict[str, Any]:
        """Reorder lessons in course."""
        try:
            result = await self._management_service.reorder_lessons(course_id, lesson_order, user_id)

            return {"result": result, "success": True}

        except Exception as e:
            logger.exception(f"Error reordering lessons in course {course_id}: {e}")
            return {"error": "Failed to reorder lessons", "success": False}

    async def duplicate_course(self, course_id: UUID, user_id: UUID, new_title: str | None = None) -> dict[str, Any]:
        """Duplicate existing course."""
        try:
            duplicate = await self._management_service.duplicate_course(course_id, user_id, new_title)

            # Initialize progress for duplicated course
            await self._progress_service.initialize_progress(duplicate.id, user_id)

            return {"course": duplicate, "success": True}

        except Exception as e:
            logger.exception(f"Error duplicating course {course_id}: {e}")
            return {"error": "Failed to duplicate course", "success": False}

    # AI operations
    async def generate_course(
        self, user_id: UUID, topic: str, skill_level: str, description: str = "", use_tools: bool = False
    ) -> dict[str, Any]:
        """Generate a new AI-powered course."""
        try:
            return await self._ai_service.process_content(
                content_type="course",
                action="generate",
                user_id=user_id,
                topic=topic,
                skill_level=skill_level,
                description=description,
                use_tools=use_tools,
            )
        except Exception as e:
            logger.exception(f"Error generating course for user {user_id}: {e}")
            raise

    async def generate_lesson_content(
        self, course_id: UUID, user_id: UUID, lesson_meta: dict[str, Any]
    ) -> tuple[str, list[dict]]:
        """Generate AI content for a lesson."""
        try:
            # Add course ID to lesson meta
            lesson_meta["course_id"] = str(course_id)

            content, citations = await self._ai_service.process_content(
                content_type="course",
                action="lesson",
                user_id=user_id,
                course_id=str(course_id),
                lesson_meta=lesson_meta,
            )
            return content, citations
        except Exception as e:
            logger.exception(f"Error generating lesson for course {course_id}: {e}")
            raise

    async def update_course_with_ai(self, course_id: UUID, user_id: UUID, updates: dict[str, Any]) -> dict[str, Any]:
        """Update course content using AI."""
        try:
            return await self._ai_service.process_content(
                content_type="course", action="update", user_id=user_id, course_id=str(course_id), updates=updates
            )
        except Exception as e:
            logger.exception(f"Error updating course {course_id} with AI: {e}")
            raise

    async def chat_about_course(
        self, course_id: UUID, user_id: UUID, message: str, history: list[dict[str, Any]] | None = None
    ) -> str:
        """Have a conversation about the course."""
        try:
            return await self._ai_service.process_content(
                content_type="course",
                action="chat",
                user_id=user_id,
                course_id=str(course_id),
                message=message,
                history=history,
            )
        except Exception as e:
            logger.exception(f"Error in course chat for {course_id}: {e}")
            raise
