"""Course progress service implementing the ProgressTracker protocol.

Provides lesson-based progress tracking for courses with completion percentage calculations.
Handles course-specific progress patterns including lesson completion, quiz results,
learning preferences, and adaptive settings.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from src.courses.models import Course, Lesson
from src.database.session import async_session_maker
from src.progress.models import ProgressUpdate
from src.progress.protocols import ProgressTracker
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


class CourseProgressService(ProgressTracker):
    """Progress service for courses with lesson-based progress tracking functionality."""

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific course and user."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, content_id)

            # Get course for total lessons count
            course_query = select(Course).where(Course.id == content_id)
            course_result = await session.execute(course_query)
            course = course_result.scalar_one_or_none()

            if not course:
                logger.warning(f"Course {content_id} not found")
                return {
                    "completion_percentage": 0,
                    "completed_lessons": {},
                    "current_lesson": "",
                    "total_lessons": 0,
                    "quiz_scores": {},
                    "learning_patterns": {},
                    "pacing_preference": "normal",
                }

            # Get total lessons count
            lessons_query = select(Lesson).where(Lesson.roadmap_id == content_id)
            lessons_result = await session.execute(lessons_query)
            lessons = lessons_result.scalars().all()
            total_lessons = len(lessons)

            if not progress_data:
                return {
                    "completion_percentage": 0,
                    "completed_lessons": {},
                    "current_lesson": lessons[0].id if lessons else "",
                    "total_lessons": total_lessons,
                    "quiz_scores": {},
                    "learning_patterns": {},
                    "pacing_preference": "normal",
                    "last_accessed_at": None,
                    "created_at": None,
                    "updated_at": None,
                }

            # Extract metadata with course-specific defaults
            metadata = progress_data.metadata or {}
            completed_lessons = metadata.get("completed_lessons", {})

            # Calculate progress percentage from completed lessons
            progress_percentage = progress_data.progress_percentage or 0
            if total_lessons > 0 and completed_lessons and progress_percentage == 0:
                try:
                    progress_percentage = self._calculate_lesson_progress_percentage(completed_lessons, total_lessons)
                except Exception as e:
                    logger.warning(f"Failed to calculate course progress percentage: {e}")
                    progress_percentage = 0

            return {
                "completion_percentage": progress_percentage,
                "completed_lessons": completed_lessons,
                "current_lesson": metadata.get("current_lesson", lessons[0].id if lessons else ""),
                "total_lessons": total_lessons,
                "quiz_scores": metadata.get("quiz_scores", {}),
                "learning_patterns": metadata.get("learning_patterns", {}),
                "pacing_preference": metadata.get("pacing_preference", "normal"),
                "last_accessed_at": progress_data.updated_at,
                "created_at": progress_data.created_at,
                "updated_at": progress_data.updated_at,
            }

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update progress data for specific course and user."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)

            # Get current progress and validate course
            current_progress, course, total_lessons = await self._get_progress_context(
                session, progress_service, user_id, content_id
            )
            if not course:
                logger.error(f"Course {content_id} not found")
                return {"error": "Course not found"}

            # Prepare metadata with existing data
            metadata = current_progress.metadata if current_progress else {}
            completion_percentage = current_progress.progress_percentage if current_progress else 0

            metadata["content_type"] = "course"
            metadata["total_lessons"] = total_lessons

            # Process different types of progress updates
            completion_percentage = await self._process_lesson_completion(
                metadata, progress_data, completion_percentage, total_lessons
            )
            await self._process_quiz_results(metadata, progress_data)
            self._process_settings_updates(metadata, progress_data)

            # Explicit completion percentage override
            if "completion_percentage" in progress_data and progress_data["completion_percentage"] is not None:
                completion_percentage = progress_data["completion_percentage"]

            # Update using unified progress service
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)
            updated = await progress_service.update_progress(user_id, content_id, "course", progress_update)

            # Return updated progress in expected format
            return self._format_progress_response(updated, metadata, total_lessons, course)

    async def _get_progress_context(
        self, session: Any, progress_service: Any, user_id: UUID, content_id: UUID
    ) -> tuple[Any, Any, int]:
        """Get current progress, course, and lesson count."""
        current_progress = await progress_service.get_single_progress(user_id, content_id)

        # Get course for validation and defaults
        course_query = select(Course).where(Course.id == content_id)
        course_result = await session.execute(course_query)
        course = course_result.scalar_one_or_none()

        # Get total lessons count
        total_lessons = 0
        if course:
            lessons_query = select(Lesson).where(Lesson.roadmap_id == content_id)
            lessons_result = await session.execute(lessons_query)
            lessons = lessons_result.scalars().all()
            total_lessons = len(lessons)

        return current_progress, course, total_lessons

    async def _process_lesson_completion(
        self, metadata: dict, progress_data: dict, completion_percentage: float, total_lessons: int
    ) -> float:
        """Process lesson completion updates."""
        if "lesson_completed" not in progress_data:
            return completion_percentage

        lesson_id = progress_data.get("lesson_id")
        is_completed = progress_data["lesson_completed"]

        if lesson_id:
            completed_lessons = metadata.get("completed_lessons", {})
            if is_completed:
                completed_lessons[lesson_id] = True
            else:
                completed_lessons.pop(lesson_id, None)

            metadata["completed_lessons"] = completed_lessons

            # Recalculate completion percentage
            completion_percentage = self._calculate_lesson_progress_percentage(completed_lessons, total_lessons)

        return completion_percentage

    async def _process_quiz_results(self, metadata: dict, progress_data: dict) -> None:
        """Process quiz results updates."""
        if "quiz_results" not in progress_data:
            return

        quiz_results = progress_data["quiz_results"]
        lesson_id = progress_data.get("lesson_id")

        if lesson_id and quiz_results:
            quiz_scores = metadata.get("quiz_scores", {})
            quiz_scores[lesson_id] = {
                "total_score": quiz_results.get("total_score", 0),
                "time_spent": quiz_results.get("time_spent", 0),
                "concepts": quiz_results.get("concepts", {}),
                "completed_at": datetime.now(UTC).isoformat(),
            }
            metadata["quiz_scores"] = quiz_scores

            # Update learning patterns based on quiz performance
            self._update_learning_patterns(metadata, lesson_id, quiz_results)

            # Performance tracking removed - no difficulty adjustments

    def _process_settings_updates(self, metadata: dict, progress_data: dict) -> None:
        """Process settings and preference updates."""
        # Update current lesson if provided
        if "current_lesson" in progress_data:
            metadata["current_lesson"] = progress_data["current_lesson"]

        # Update course settings/preferences
        if "pacing_preference" in progress_data:
            metadata["pacing_preference"] = progress_data["pacing_preference"]

    def _format_progress_response(self, updated: Any, metadata: dict, total_lessons: int, _course: Any) -> dict:
        """Format the progress response."""
        return {
            "completion_percentage": updated.progress_percentage,
            "completed_lessons": metadata.get("completed_lessons", {}),
            "current_lesson": metadata.get("current_lesson", ""),
            "total_lessons": total_lessons,
            "quiz_scores": metadata.get("quiz_scores", {}),
            "learning_patterns": metadata.get("learning_patterns", {}),
            "difficulty_preference": metadata.get("difficulty_preference", "beginner"),
            "pacing_preference": metadata.get("pacing_preference", "normal"),
            "last_accessed_at": updated.updated_at,
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }

    async def mark_lesson_complete(
        self, content_id: UUID, user_id: UUID, lesson_id: str, completed: bool = True
    ) -> None:
        """Mark a course lesson as complete or incomplete."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            # Get current metadata
            metadata = current_progress.metadata if current_progress else {}
            completed_lessons = metadata.get("completed_lessons", {})

            # Update lesson status
            if completed:
                completed_lessons[lesson_id] = True
            else:
                completed_lessons.pop(lesson_id, None)

            metadata["completed_lessons"] = completed_lessons

            # Get total lessons for percentage calculation
            total_lessons = metadata.get("total_lessons", 0)
            if total_lessons == 0:
                lessons_query = select(Lesson).where(Lesson.roadmap_id == content_id)
                lessons_result = await session.execute(lessons_query)
                lessons = lessons_result.scalars().all()
                total_lessons = len(lessons)
                metadata["total_lessons"] = total_lessons

            # Recalculate completion percentage
            completion_percentage = self._calculate_lesson_progress_percentage(completed_lessons, total_lessons)

            # Update progress
            progress_update = ProgressUpdate(progress_percentage=completion_percentage, metadata=metadata)
            await progress_service.update_progress(user_id, content_id, "course", progress_update)

    async def update_course_settings(self, content_id: UUID, user_id: UUID, settings: dict[str, Any]) -> dict[str, Any]:
        """Update course-specific settings and preferences."""
        async with async_session_maker() as session:
            progress_service = ProgressService(session)
            current_progress = await progress_service.get_single_progress(user_id, content_id)

            if current_progress:
                metadata = current_progress.metadata.copy() if current_progress.metadata else {}

                # Update supported settings
                supported_settings = ["pacing_preference", "current_lesson", "learning_patterns"]

                for setting in supported_settings:
                    if setting in settings:
                        metadata[setting] = settings[setting]

                progress_update = ProgressUpdate(
                    progress_percentage=current_progress.progress_percentage, metadata=metadata
                )

                await progress_service.update_progress(user_id, content_id, "course", progress_update)

            return settings

    async def get_lesson_completion_stats(self, course_id: UUID, user_id: UUID) -> dict:
        """Get detailed lesson completion statistics for a course."""
        async with async_session_maker() as session:
            # Get course
            course_query = select(Course).where(Course.id == course_id)
            course_result = await session.execute(course_query)
            course = course_result.scalar_one_or_none()

            if not course:
                return {
                    "total_lessons": 0,
                    "completed_lessons": 0,
                    "lesson_percentage": 0,
                    "quiz_average_score": 0,
                    "time_spent_minutes": 0,
                    "learning_velocity": "normal",
                }

            # Get lessons for this course
            lessons_query = select(Lesson).where(Lesson.roadmap_id == course_id)
            lessons_result = await session.execute(lessons_query)
            lessons = lessons_result.scalars().all()
            total_lessons = len(lessons)

            # Get progress from unified service
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, course_id)

            if not progress_data or not progress_data.metadata:
                return {
                    "total_lessons": total_lessons,
                    "completed_lessons": 0,
                    "lesson_percentage": 0,
                    "quiz_average_score": 0,
                    "time_spent_minutes": 0,
                    "learning_velocity": "normal",
                }

            metadata = progress_data.metadata
            completed_lessons_dict = metadata.get("completed_lessons", {})
            quiz_scores = metadata.get("quiz_scores", {})

            # Calculate completion stats
            completed_count = len([k for k, v in completed_lessons_dict.items() if v])
            lesson_percentage = int((completed_count / total_lessons) * 100) if total_lessons > 0 else 0

            # Calculate quiz statistics
            quiz_average_score = 0
            total_time_spent = 0

            if quiz_scores:
                total_score = sum(score_data.get("total_score", 0) for score_data in quiz_scores.values())
                total_time_spent = sum(score_data.get("time_spent", 0) for score_data in quiz_scores.values())
                quiz_average_score = total_score / len(quiz_scores) if quiz_scores else 0

            # Determine learning velocity based on completion rate and quiz performance
            learning_velocity = self._calculate_learning_velocity(
                completed_count, total_lessons, quiz_average_score, total_time_spent
            )

            return {
                "total_lessons": total_lessons,
                "completed_lessons": completed_count,
                "lesson_percentage": lesson_percentage,
                "quiz_average_score": quiz_average_score,
                "time_spent_minutes": total_time_spent // 60,  # Convert seconds to minutes
                "learning_velocity": learning_velocity,
                "pacing_preference": metadata.get("pacing_preference", "normal"),
            }

    def _calculate_lesson_progress_percentage(self, completed_lessons: dict, total_lessons: int) -> float:
        """Calculate progress percentage based on completed lessons."""
        if total_lessons == 0:
            return 0.0

        completed_count = len([k for k, v in completed_lessons.items() if v])
        percentage = (completed_count / total_lessons) * 100

        logger.info(f"📚 Course progress: {completed_count}/{total_lessons} lessons = {percentage:.1f}%")
        return min(percentage, 100.0)

    def _update_learning_patterns(self, metadata: dict, _lesson_id: str, quiz_results: dict) -> None:
        """Update learning patterns based on quiz performance."""
        learning_patterns = metadata.get("learning_patterns", {})

        # Analyze concept performance
        concepts = quiz_results.get("concepts", {})
        total_score = quiz_results.get("total_score", 0)
        time_spent = quiz_results.get("time_spent", 0)

        # Update concept strengths/weaknesses
        for concept, score in concepts.items():
            if concept not in learning_patterns:
                learning_patterns[concept] = {"scores": [], "avg_score": 0}

            learning_patterns[concept]["scores"].append(score)
            # Keep only last 5 scores to track recent performance
            if len(learning_patterns[concept]["scores"]) > 5:
                learning_patterns[concept]["scores"] = learning_patterns[concept]["scores"][-5:]

            learning_patterns[concept]["avg_score"] = sum(learning_patterns[concept]["scores"]) / len(
                learning_patterns[concept]["scores"]
            )

        # Track overall performance trends
        if "overall_performance" not in learning_patterns:
            learning_patterns["overall_performance"] = {"scores": [], "time_efficiency": []}

        learning_patterns["overall_performance"]["scores"].append(total_score)
        if time_spent > 0:
            efficiency = total_score / (time_spent / 60)  # Score per minute
            learning_patterns["overall_performance"]["time_efficiency"].append(efficiency)

        # Keep only recent data
        for key in ["scores", "time_efficiency"]:
            if len(learning_patterns["overall_performance"].get(key, [])) > 10:
                learning_patterns["overall_performance"][key] = learning_patterns["overall_performance"][key][-10:]

        metadata["learning_patterns"] = learning_patterns

    def _calculate_learning_velocity(
        self, completed_lessons: int, total_lessons: int, avg_quiz_score: float, _time_spent_seconds: int
    ) -> str:
        """Calculate learning velocity based on completion rate and performance."""
        if total_lessons == 0:
            return "normal"

        completion_rate = completed_lessons / total_lessons

        # High completion rate + good scores = fast learner
        if completion_rate > 0.7 and avg_quiz_score > 80:
            return "fast"
        # Low completion rate or poor scores = needs more time
        if completion_rate < 0.3 or avg_quiz_score < 60:
            return "slow"
        return "normal"
