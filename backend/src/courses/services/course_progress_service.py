"""Course progress service implementing the ProgressTracker protocol.

Provides lesson-based progress tracking for courses with completion percentage calculations.
Handles course-specific progress patterns including lesson completion, quiz results,
learning preferences, and adaptive settings.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select

from src.courses.models import Course, CourseConcept, Lesson, UserConceptState
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

            # Determine total units for progress
            # Standard: number of lessons. Adaptive: number of concepts assigned to course.
            lessons_query = select(Lesson).where(Lesson.course_id == content_id)
            lessons_result = await session.execute(lessons_query)
            lessons = lessons_result.scalars().all()
            total_lessons = len(lessons)

            if course.adaptive_enabled:
                # COUNT concepts for adaptive courses
                concept_count = await session.scalar(
                    select(func.count()).select_from(CourseConcept).where(CourseConcept.course_id == content_id)
                )
                total_concepts = int(concept_count or 0)
                if total_concepts > 0:
                    total_lessons = total_concepts

                # Compute avg mastery over assigned concepts (missing state = 0.0)
                avg_mastery_stmt = (
                    select(func.avg(func.coalesce(UserConceptState.s_mastery, 0.0)))
                    .select_from(
                        CourseConcept.__table__.outerjoin(
                            UserConceptState.__table__,
                            and_(
                                UserConceptState.concept_id == CourseConcept.concept_id,
                                UserConceptState.user_id == user_id,
                            ),
                        )
                    )
                    .where(CourseConcept.course_id == content_id)
                )
                avg_mastery = await session.scalar(avg_mastery_stmt)
                progress_percentage = round(float(avg_mastery or 0.0) * 100.0, 2)

                # Current lesson fallback (use stored metadata if present; else first lesson)
                metadata = (progress_data.metadata if progress_data else {}) or {}
                current_lesson = metadata.get("current_lesson") or metadata.get("current_lesson_id") or (
                    lessons[0].id if lessons else ""
                )

                return {
                    "completion_percentage": progress_percentage,
                    "completed_lessons": metadata.get("completed_lessons", []),
                    "current_lesson": current_lesson,
                    "total_lessons": total_lessons,
                    "quiz_scores": metadata.get("quiz_scores", {}),
                    "learning_patterns": metadata.get("learning_patterns", {}),
                    "concept_review_stats": metadata.get("concept_review_stats", {}),
                    "last_reviewed_concept": metadata.get("last_reviewed_concept"),
                    "last_reviewed_rating": metadata.get("last_reviewed_rating"),
                    "last_review_duration_ms": metadata.get("last_review_duration_ms"),
                    "last_reviewed_at": metadata.get("last_reviewed_at"),
                    "last_next_review_at": metadata.get("last_next_review_at"),
                }

            if not progress_data:
                return {
                    "completion_percentage": 0,
                    "completed_lessons": [],
                    "current_lesson": lessons[0].id if lessons else "",
                    "total_lessons": total_lessons,
                    "quiz_scores": {},
                    "learning_patterns": {},
                    "pacing_preference": "normal",
                    "last_accessed_at": None,
                    "created_at": None,
                    "updated_at": None,
                }

            # Extract metadata with course-specific defaults (non-adaptive path)
            metadata = progress_data.metadata or {}

            # Normalize completed_lessons to a list of lesson IDs
            raw_completed = metadata.get("completed_lessons", []) or []
            if isinstance(raw_completed, dict):
                completed_list = [lid for lid, flag in raw_completed.items() if flag]
            elif isinstance(raw_completed, list):
                completed_list = list({str(x) for x in raw_completed})
            else:
                completed_list = []

            # Calculate progress percentage from completed lessons
            progress_percentage = progress_data.progress_percentage or 0
            if total_lessons > 0 and completed_list and progress_percentage == 0:
                try:
                    progress_percentage = self._calculate_lesson_progress_percentage_dictsafe(completed_list, total_lessons)
                except Exception as e:
                    logger.warning(f"Failed to calculate course progress percentage: {e}")
                    progress_percentage = 0

            return {
                "completion_percentage": progress_percentage,
                "completed_lessons": completed_list,
                "current_lesson": metadata.get("current_lesson")
                or metadata.get("current_lesson_id")
                or (lessons[0].id if lessons else ""),
                "total_lessons": total_lessons,
                "quiz_scores": metadata.get("quiz_scores", {}),
                "learning_patterns": metadata.get("learning_patterns", {}),
            }

    async def calculate_completion_percentage(self, content_id: UUID, user_id: UUID) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        progress = await self.get_progress(content_id, user_id)
        return progress.get("completion_percentage", 0.0)

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
            self._update_concept_review_stats(metadata, progress_data)
            self._update_recent_review_metadata(metadata, progress_data)

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

        # Get total lessons/concepts count
        total_lessons = 0
        if course:
            # Default to lesson count
            lessons_query = select(Lesson).where(Lesson.course_id == content_id)
            lessons_result = await session.execute(lessons_query)
            lessons = lessons_result.scalars().all()
            total_lessons = len(lessons)

            # For adaptive courses, use assigned concept count as the unit of progress
            if course.adaptive_enabled:
                concept_count = await session.scalar(
                    select(func.count()).select_from(CourseConcept).where(CourseConcept.course_id == content_id)
                )
                if concept_count and int(concept_count) > 0:
                    total_lessons = int(concept_count)

        return current_progress, course, total_lessons

    async def _process_lesson_completion(
        self, metadata: dict, progress_data: dict, completion_percentage: float, total_lessons: int
    ) -> float:
        """Process lesson completion updates (stores a list of completed lesson ids)."""
        if "lesson_completed" not in progress_data:
            return completion_percentage

        lesson_id = progress_data.get("lesson_id")
        is_completed = progress_data["lesson_completed"]

        # Normalize existing value to a set
        raw_completed = metadata.get("completed_lessons", []) or []
        if isinstance(raw_completed, dict):
            completed_set = {str(lid) for lid, flag in raw_completed.items() if flag}
        elif isinstance(raw_completed, list):
            completed_set = {str(x) for x in raw_completed}
        else:
            completed_set = set()

        if lesson_id:
            lid = str(lesson_id)
            if is_completed:
                completed_set.add(lid)
            else:
                completed_set.discard(lid)

        # Persist back as a list (canonical form)
        completed_list = sorted(completed_set)
        metadata["completed_lessons"] = completed_list

        # Recalculate completion percentage for non-adaptive courses only
        if total_lessons > 0:
            completion_percentage = self._calculate_lesson_progress_percentage_dictsafe(completed_list, total_lessons)

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

    def _update_concept_review_stats(self, metadata: dict, progress_data: dict) -> None:
        """Merge per-concept review telemetry into metadata."""
        incoming = progress_data.get("concept_review_stats")
        if not incoming:
            return

        existing = metadata.get("concept_review_stats") or {}
        for concept_id, concept_payload in incoming.items():
            current_stats = existing.get(concept_id, {})
            rating_counts = current_stats.get("ratingCounts", {"1": 0, "2": 0, "3": 0, "4": 0})
            for rating_key, count in concept_payload.get("ratingCounts", {}).items():
                rating_counts[rating_key] = int(rating_counts.get(rating_key, 0)) + int(count)
            current_stats["ratingCounts"] = rating_counts

            current_stats["totalDurationMs"] = int(current_stats.get("totalDurationMs", 0)) + int(
                concept_payload.get("totalDurationMs", 0)
            )

            for key in (
                "lastRating",
                "lastDurationMs",
                "lastReviewedAt",
                "lastNextReviewAt",
                "mastery",
                "exposures",
            ):
                if key in concept_payload and concept_payload[key] is not None:
                    current_stats[key] = concept_payload[key]

            existing[concept_id] = current_stats

        metadata["concept_review_stats"] = existing

    def _update_recent_review_metadata(self, metadata: dict, progress_data: dict) -> None:
        """Persist surface-level metadata about the latest review."""
        for key in (
            "last_reviewed_concept",
            "last_reviewed_rating",
            "last_review_duration_ms",
            "last_reviewed_at",
            "last_next_review_at",
        ):
            if key in progress_data and progress_data[key] is not None:
                metadata[key] = progress_data[key]

    def _format_progress_response(self, updated: Any, metadata: dict, total_lessons: int, _course: Any) -> dict:
        """Format the progress response."""
        completed_lessons = metadata.get("completed_lessons", [])
        if isinstance(completed_lessons, dict):
            completed_lessons = [str(lid) for lid, flag in completed_lessons.items() if flag]
        elif isinstance(completed_lessons, (set, tuple)):
            completed_lessons = [str(lid) for lid in completed_lessons]
        else:
            completed_lessons = [str(lid) for lid in completed_lessons] if isinstance(completed_lessons, list) else []

        return {
            "completion_percentage": updated.progress_percentage,
            "completed_lessons": completed_lessons,
            "current_lesson": metadata.get("current_lesson", ""),
            "total_lessons": total_lessons,
            "quiz_scores": metadata.get("quiz_scores", {}),
            "learning_patterns": metadata.get("learning_patterns", {}),
            "concept_review_stats": metadata.get("concept_review_stats", {}),
            "last_reviewed_concept": metadata.get("last_reviewed_concept"),
            "last_reviewed_rating": metadata.get("last_reviewed_rating"),
            "last_review_duration_ms": metadata.get("last_review_duration_ms"),
            "last_reviewed_at": metadata.get("last_reviewed_at"),
            "last_next_review_at": metadata.get("last_next_review_at"),
            "difficulty_preference": metadata.get("difficulty_preference", "beginner"),
            "pacing_preference": metadata.get("pacing_preference", "normal"),
            "last_accessed_at": updated.updated_at,
            "created_at": updated.created_at,
            "updated_at": updated.updated_at,
        }



    def _calculate_lesson_progress_percentage_dictsafe(self, completed_lessons: list[str], total_lessons: int) -> float:
        """Calculate progress percentage based on completed lessons (list form)."""
        if total_lessons == 0:
            return 0.0

        completed_count = len(completed_lessons)
        percentage = (completed_count / total_lessons) * 100
        logger.info(f"📚 Course progress: {completed_count}/{total_lessons} lessons = {percentage:.1f}%")
        return min(round(percentage, 2), 100.0)

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

