"""
Courses Module Facade.

Single entry point for all course/roadmap-related operations.
Coordinates internal course services and provides stable API for other modules.
"""

import json
import logging
from typing import Any
from uuid import UUID

from src.ai.service import get_ai_service

from .services.course_content_service import CourseContentService
from .services.course_progress_service import CourseProgressService
from .services.course_query_service import CourseQueryService


logger = logging.getLogger(__name__)


class CoursesFacade:
    """
    Single entry point for all course/roadmap operations.

    Coordinates internal course services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Don't initialize with sessions - create on-demand
        self._content_service = CourseContentService()  # New base service
        self._progress_service = CourseProgressService()  # Handles lesson progress tracking
        self._ai_service = get_ai_service()

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get course with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_course_with_progress(content_id, user_id)

    async def get_course_with_progress(self, course_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get complete course information with progress.

        Coordinates course service and progress service to provide comprehensive data.
        """
        try:
            # Get course information using query service
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                query_service = CourseQueryService(session)
                course_response = await query_service.get_course(course_id, user_id)
                course = course_response.model_dump() if course_response else None

            if not course:
                return {"error": "Course not found", "success": False}

            # Get progress data from progress service
            progress = await self._progress_service.get_progress(course_id, user_id)
            completion_percentage = progress.get("completion_percentage", 0)
            completed_lessons = progress.get("completed_lessons", {})
            current_lesson = progress.get("current_lesson", "")
            total_lessons = progress.get("total_lessons", 0)

            return {
                "course": course,
                "progress": progress,
                "completion_percentage": completion_percentage,
                "current_lesson": current_lesson,
                "total_lessons": total_lessons,
                "completed_lessons": completed_lessons,
                "success": True,
            }

        except Exception:
            logger.exception("Error getting course %s for user %s", course_id, user_id)
            return {"error": "Failed to retrieve course", "success": False}

    async def create_course(self, course_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Create new course entry.

        Handles course creation and coordinates all related operations.
        """
        try:
            # Use the content service which handles tags, progress, and AI processing
            course = await self._content_service.create_course(course_data, user_id)

            return {"course": course, "success": True}

        except Exception:
            logger.exception("Error creating course for user %s", user_id)
            return {"error": "Failed to create course", "success": False}

    # NOTE: Auto-tagging removed - now handled by CourseContentService via BaseContentService pipeline
    # Tagging happens automatically during course creation/updates, no manual intervention needed

    async def generate_ai_course(self, topic: str, preferences: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """
        Generate AI-powered course from topic.

        Handles AI course generation and coordinates related operations.
        """
        try:
            # Build course data combining provided preferences and required fields
            data: dict[str, Any] = {**(preferences or {})}
            data["prompt"] = topic  # Use prompt field for AI generation

            # Use the content service which handles tags, progress, and AI processing automatically
            course = await self._content_service.create_course(data, user_id)

            return {"course": course, "success": True}

        except Exception as e:
            logger.exception(f"Error generating AI course {topic} for user {user_id}: {e}")
            return {"error": f"Failed to generate course: {e!s}", "success": False}

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

        Handles progress updates, lesson tracking, and completion detection.
        """
        try:
            updated_progress = await self._progress_service.update_progress(course_id, user_id, progress_data)
            return {"progress": updated_progress, "success": True}

        except Exception as e:
            logger.exception(f"Error updating progress for course {course_id}: {e}")
            return {"error": f"Failed to update progress: {e!s}", "success": False}

    async def update_course(self, course_id: UUID, user_id: UUID, update_data: dict[str, Any]) -> dict[str, Any]:
        """
        Update course metadata.

        Updates course information and coordinates any needed reprocessing.
        """
        try:
            # Update through content service which handles tags and reprocessing
            course = await self._content_service.update_course(course_id, update_data, user_id)

            return {"course": course, "success": True}

        except Exception:
            logger.exception("Error updating course %s", course_id)
            return {"error": "Failed to update course", "success": False}

    async def search_courses(self, query: str, user_id: UUID, filters: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Search user's courses.

        Provides unified search across course content and metadata.
        """
        try:
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                query_service = CourseQueryService(session)
                limit = (filters or {}).get("limit", 20)
                results, _total = await query_service.list_courses(per_page=limit, search=query, user_id=user_id)

            return {"results": results, "success": True}

        except Exception:
            logger.exception("Error searching courses for user %s", user_id)
            return {"error": "Search failed", "success": False}

    async def get_user_courses(self, user_id: UUID, include_progress: bool = True) -> dict[str, Any]:
        """
        Get all courses for user.

        Optionally includes progress information.
        """
        try:
            from src.courses.services.course_response_builder import CourseResponseBuilder
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                # Fetch courses for this user
                from sqlalchemy import select

                from src.courses.models import Course

                result = await session.execute(
                    select(Course).where(Course.user_id == user_id).order_by(Course.created_at.desc())
                )
                courses = list(result.scalars().all())

                # Convert to response objects for consistent schema
                course_responses = CourseResponseBuilder.build_course_list(courses)

                # Convert to dict format and optionally add progress
                course_dicts: list[dict[str, Any]] = []
                for cr in course_responses:
                    cd = cr.model_dump()
                    if include_progress:
                        try:
                            # Get actual progress data from progress service
                            progress = await self._progress_service.get_progress(cr.id, user_id)
                            cd["progress"] = progress
                        except Exception as e:
                            logger.warning(f"Failed to get progress for course {cr.id}: {e}")
                            cd["progress"] = {"completion_percentage": 0, "completed_lessons": {}}
                    course_dicts.append(cd)

            return {"courses": course_dicts, "success": True}

        except Exception as e:
            logger.exception(f"Error getting courses for user {user_id}: {e}")
            return {"error": f"Failed to get courses: {e!s}", "success": False}

    async def delete_course(self, db: Any, course_id: UUID, user_id: UUID) -> None:
        """
        Delete a course.

        Args:
            db: Database session
            course_id: Course ID to delete
            user_id: User ID for ownership validation

        Raises
        ------
            ValueError: If course not found or user doesn't own it
        """
        from sqlalchemy import select

        from src.courses.models import Course

        # Get course with user validation
        query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
        result = await db.execute(query)
        course = result.scalar_one_or_none()

        if not course:
            msg = f"Course {course_id} not found"
            raise ValueError(msg)

        # Delete the course (cascade handles related records)
        await db.delete(course)
        # Note: Commit is handled by the caller (content_service)

        # Delete RAG chunks (best-effort, will be done after caller commits)
        try:
            from src.ai.rag.service import RAGService

            chunks_deleted = await RAGService.delete_chunks_by_course_id(db, str(course_id))
            if chunks_deleted > 0:
                logger.info(f"Deleted {chunks_deleted} RAG chunks for course {course_id}")
        except Exception as e:
            # Log but don't fail - this is best-effort cleanup
            logger.warning(f"Could not delete RAG chunks for course {course_id}: {e}")

        logger.info(f"Deleted course {course_id}")

    async def get_course_lessons(self, course_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get course lessons/outline if available."""
        try:
            # Get database session
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                # Fetch course to read lessons structure
                from sqlalchemy import select

                from src.courses.models import Course

                result = await session.execute(select(Course).where(Course.id == course_id, Course.user_id == user_id))
                course = result.scalar_one_or_none()
                if not course:
                    logger.info(f"Course {course_id} not found for user {user_id}")
                    return {"error": f"Course {course_id} not found", "success": False}

                lessons: list[dict] = []
                if getattr(course, "lessons_outline", None):
                    try:
                        outline = json.loads(course.lessons_outline)  # type: ignore[arg-type]
                        if isinstance(outline, list):
                            lessons = outline
                    except (json.JSONDecodeError, TypeError):
                        lessons = []

                # Add progress information for each lesson
                if lessons:
                    try:
                        # Get progress data to check lesson completion
                        progress = await self._progress_service.get_progress(course_id, user_id)
                        completed_lessons = progress.get("completed_lessons", {})

                        # Mark lessons as completed or not based on actual progress
                        for lesson in lessons:
                            lesson_id = lesson.get("id", "")
                            lesson["completed"] = completed_lessons.get(str(lesson_id), False)
                    except Exception as e:
                        logger.warning(f"Failed to get lesson progress for course {course_id}: {e}")
                        # Fallback: mark all as not completed
                        for lesson in lessons:
                            lesson["completed"] = False

                return {"lessons": lessons or [], "success": True}

        except Exception:
            logger.exception("Error getting lessons for course %s", course_id)
            return {"error": "Failed to get lessons", "success": False}

    # Lesson-specific operations for router compatibility
    async def get_lesson_simplified(
        self, course_id: UUID, lesson_id: UUID, generate: bool = False, user_id: UUID | None = None
    ) -> Any:
        """Get a specific lesson by course and lesson ID.

        Passes user_id through to ensure authenticated generation and user isolation.
        """
        try:
            from src.courses.services.lesson_service import LessonService
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                if not user_id:
                    from fastapi import HTTPException

                    raise HTTPException(status_code=401, detail="User authentication required")
                lesson_service = LessonService(session, user_id)
                return await lesson_service.get_lesson(course_id, lesson_id, generate)

        except Exception:
            logger.exception("Error getting lesson %s for course %s", lesson_id, course_id)
            raise
