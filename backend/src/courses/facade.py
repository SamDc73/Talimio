"""
Courses Module Facade.

Single entry point for all course-related operations.
Coordinates internal course services and provides stable API for other modules.
"""

import logging
from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Course
from src.database.session import async_session_maker

from .services.course_content_service import CourseContentService
from .services.course_progress_service import CourseProgressService
from .services.course_query_service import CourseQueryService


logger = logging.getLogger(__name__)


class CoursesFacade:
    """
    Single entry point for all course operations.

    Coordinates internal course services, publishes events, and provides
    stable API that won't break when internal implementation changes.
    """

    def __init__(self) -> None:
        # Don't initialize with sessions - create on-demand
        self._content_service = CourseContentService()  # New base service
        self._progress_service = CourseProgressService()  # Handles lesson progress tracking

    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """
        Get course with progress information.

        Implements ContentFacade interface for consistent cross-module API.
        """
        return await self.get_course(content_id, user_id)

    async def get_course(
        self,
        course_id: UUID,
        user_id: UUID,
        session: AsyncSession | None = None,
    ) -> dict[str, Any]:
        """
        Get complete course information with progress.

        Coordinates course service and progress service to provide comprehensive data.
        """
        try:
            if session is not None:
                query_service = CourseQueryService(session)
                course_response = await query_service.get_course(course_id, user_id)
            else:
                async with async_session_maker() as query_session:
                    query_service = CourseQueryService(query_session)
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

    async def create_course(
        self,
        course_data: dict[str, Any],
        user_id: UUID,
        session: AsyncSession | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, Any]:
        """
        Create new course entry.

        Handles course creation and coordinates all related operations.
        """
        try:
            # Use the content service which handles tags, progress, and AI processing
            created_course = await self._content_service.create_course(
                course_data,
                user_id,
                session=session,
                background_tasks=background_tasks,
            )

            if session is not None:
                query_service = CourseQueryService(session)
                course_response = await query_service.get_course(created_course.id, user_id)
            else:
                async with async_session_maker() as query_session:
                    query_service = CourseQueryService(query_session)
                    course_response = await query_service.get_course(created_course.id, user_id)

            return {"course": course_response, "success": True}

        except Exception:
            logger.exception("Error creating course for user %s", user_id)
            return {"error": "Failed to create course", "success": False}

    # NOTE: Auto-tagging removed - now handled by CourseContentService via BaseContentService pipeline
    # Tagging happens automatically during course creation/updates, no manual intervention needed

    async def generate_ai_course(
        self,
        topic: str,
        preferences: dict[str, Any],
        user_id: UUID,
        session: AsyncSession | None = None,
        background_tasks: BackgroundTasks | None = None,
    ) -> dict[str, Any]:
        """
        Generate AI-powered course from topic.

        Handles AI course generation and coordinates related operations.
        """
        try:
            # Build course data combining provided preferences and required fields
            data: dict[str, Any] = {**(preferences or {})}
            data["prompt"] = topic  # Use prompt field for AI generation

            # Use the content service which handles tags, progress, and AI processing automatically
            course = await self._content_service.create_course(
                data,
                user_id,
                session=session,
                background_tasks=background_tasks,
            )

            if session is not None:
                query_service = CourseQueryService(session)
                course_response = await query_service.get_course(course.id, user_id)
            else:
                async with async_session_maker() as query_session:
                    query_service = CourseQueryService(query_session)
                    course_response = await query_service.get_course(course.id, user_id)

            return {"course": course_response, "success": True}

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
        """Update course metadata."""
        try:
            # Update through content service which handles tags and reprocessing
            updated_course = await self._content_service.update_course(course_id, update_data, user_id)

            async with async_session_maker() as session:
                query_service = CourseQueryService(session)
                course_response = await query_service.get_course(updated_course.id, user_id)

            return {"course": course_response, "success": True}

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
            async with async_session_maker() as session:
                query_service = CourseQueryService(session)
                # Simple: grab first 1000; real pagination handled at router when needed
                course_responses, _total = await query_service.list_courses(
                    page=1, per_page=1000, search=None, user_id=user_id
                )

                course_dicts: list[dict[str, Any]] = []
                for cr in course_responses:
                    cd = cr.model_dump()
                    if include_progress:
                        try:
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
        # Get course with user validation
        query = select(Course).where(Course.id == course_id, Course.user_id == user_id)
        result = await db.execute(query)
        course = result.scalar_one_or_none()

        if not course:
            msg = f"Course {course_id} not found"
            raise ValueError(msg)

        # Delete unified progress (user_progress) for this user+course (no FK cascade exists)
        try:
            from sqlalchemy import text  # local import to avoid broad module import churn

            await db.execute(
                text(
                    "DELETE FROM user_progress "
                    "WHERE user_id = :user_id AND content_id = :content_id AND content_type = 'course'"
                ),
                {"user_id": str(user_id), "content_id": str(course_id)},
            )
            logger.info("Deleted progress for course", extra={"user_id": str(user_id), "course_id": str(course_id)})
        except Exception as e:
            # Log but don't fail course deletion
            logger.warning(
                "Failed to delete progress for course",
                extra={"user_id": str(user_id), "course_id": str(course_id), "error": str(e)},
            )

        # Delete tag associations for this user+course (no FK cascade exists)
        try:
            from sqlalchemy import and_, delete  # local import to mirror books cleanup pattern

            from src.tagging.models import TagAssociation

            await db.execute(
                delete(TagAssociation).where(
                    and_(
                        TagAssociation.content_id == course.id,
                        TagAssociation.content_type == "course",
                        TagAssociation.user_id == user_id,
                    )
                )
            )
            logger.info(
                "Deleted tag associations for course",
                extra={"user_id": str(user_id), "course_id": str(course_id)},
            )
        except Exception as e:
            logger.warning(
                "Failed to delete tag associations for course",
                extra={"user_id": str(user_id), "course_id": str(course_id), "error": str(e)},
            )

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
        """Get course lessons grouped by modules."""
        try:
            try:
                async with async_session_maker() as session:
                    query_service = CourseQueryService(session)
                    course_response = await query_service.get_course(course_id, user_id)
            except HTTPException as exc:
                if exc.status_code == 404:
                    logger.info(f"Course {course_id} not found for user {user_id}")
                    return {"error": f"Course {course_id} not found", "success": False}
                raise

            progress = await self._progress_service.get_progress(course_id, user_id)
            completed_lessons = progress.get("completed_lessons", {}) if isinstance(progress, dict) else {}

            lessons_payload: list[dict[str, Any]] = []
            for module in course_response.modules:
                for lesson in module.lessons:
                    lesson_dict = lesson.model_dump()
                    lesson_dict["moduleTitle"] = module.title
                    lesson_dict["moduleId"] = str(module.id)
                    lesson_dict["completed"] = completed_lessons.get(str(lesson.id), False)
                    lessons_payload.append(lesson_dict)

            return {"lessons": lessons_payload, "success": True}

        except Exception:
            logger.exception("Error getting lessons for course %s", course_id)
            return {"error": "Failed to get lessons", "success": False}

