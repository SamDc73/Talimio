
import uuid

from sqlalchemy.ext.asyncio import AsyncSession


"""Course progress service implementing the ProgressTracker protocol.

Provides lesson-based progress tracking for courses with completion percentage calculations.
Handles course-specific progress patterns including lesson completion, quiz results,
learning preferences, and adaptive settings.
"""


import logging
from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from pydantic import JsonValue
from sqlalchemy import and_, func, select

from src.courses.models import Course, CourseConcept, Lesson, UserConceptState
from src.exceptions import NotFoundError
from src.progress.models import ProgressResponse, ProgressUpdate
from src.progress.protocols import ProgressTracker
from src.progress.service import ProgressService


logger = logging.getLogger(__name__)


type ProgressMetadata = dict[str, object]
type ProgressUpdatePayload = Mapping[str, object]
type CourseProgressPayload = dict[str, object]


def _int_value(value: object) -> int:
    return int(value) if isinstance(value, str | int | float) and not isinstance(value, bool) else 0


def _completed_lesson_ids(value: object) -> list[str]:
    if isinstance(value, dict):
        return [str(lesson_id) for lesson_id, is_completed in value.items() if is_completed]
    if isinstance(value, list | set | tuple):
        return [str(lesson_id) for lesson_id in value]
    return []


class CourseProgressService(ProgressTracker):
    """Progress service for courses with lesson-based progress tracking functionality."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_progress(self, content_id: uuid.UUID, user_id: uuid.UUID) -> CourseProgressPayload:
        """Get progress data for specific course and user."""

        async def _inner(session: AsyncSession) -> CourseProgressPayload:
            progress_service = ProgressService(session)
            progress_data = await progress_service.get_single_progress(user_id, content_id)

            # Get course for total lessons count.
            course = (await session.execute(select(Course).where(Course.id == content_id))).scalar_one_or_none()

            if not course:
                logger.warning("Course %s not found", content_id)
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
            lessons = (await session.execute(select(Lesson).where(Lesson.course_id == content_id))).scalars().all()
            total_lessons = len(lessons)

            if course.adaptive_enabled:
                # COUNT concepts for adaptive courses
                total_concepts = int(
                    (
                        await session.scalar(
                            select(func.count()).select_from(CourseConcept).where(CourseConcept.course_id == content_id)
                        )
                    )
                    or 0
                )
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
                current_lesson = (
                    metadata.get("current_lesson")
                    or metadata.get("current_lesson_id")
                    or (lessons[0].id if lessons else "")
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
            completed_list = list(set(_completed_lesson_ids(metadata.get("completed_lessons"))))

            # Calculate progress percentage from completed lessons
            progress_percentage = progress_data.progress_percentage or 0
            if total_lessons > 0 and completed_list and progress_percentage == 0:
                try:
                    progress_percentage = self._calculate_lesson_progress_percentage_dictsafe(
                        completed_list, total_lessons
                    )
                except (TypeError, ValueError, ZeroDivisionError) as e:
                    logger.warning("Failed to calculate course progress percentage: %s", e)
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

        return await _inner(self._session)

    async def calculate_completion_percentage(self, content_id: uuid.UUID, user_id: uuid.UUID) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        progress = await self.get_progress(content_id, user_id)
        value = progress.get("completion_percentage", 0.0)
        return float(value) if isinstance(value, str | int | float) else 0.0

    async def update_progress(
        self, content_id: uuid.UUID, user_id: uuid.UUID, progress_data: ProgressUpdatePayload
    ) -> CourseProgressPayload:
        """Update progress data for specific course and user."""

        async def _inner(session: AsyncSession) -> CourseProgressPayload:
            progress_service = ProgressService(session)

            # Get current progress and validate course
            current_progress, course, total_lessons = await self._get_progress_context(
                session, progress_service, user_id, content_id
            )
            if not course:
                logger.error("Course %s not found", content_id)
                resource_type = "course"
                raise NotFoundError(resource_type, str(content_id))

            # Prepare metadata with existing data
            metadata = cast("ProgressMetadata", current_progress.metadata if current_progress else {})
            completion_percentage = current_progress.progress_percentage if current_progress else 0.0
            if completion_percentage is None:
                completion_percentage = 0.0

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
                value = progress_data["completion_percentage"]
                if isinstance(value, str | int | float):
                    completion_percentage = float(value)

            # Update using unified progress service
            progress_update = ProgressUpdate(
                progress_percentage=completion_percentage,
                metadata=cast("dict[str, JsonValue]", metadata),
            )
            updated = await progress_service.update_progress(user_id, content_id, "course", progress_update)

            # Return updated progress in expected format
            return self._format_progress_response(updated, metadata, total_lessons, course)

        return await _inner(self._session)

    async def _get_progress_context(
        self, session: AsyncSession, progress_service: ProgressService, user_id: uuid.UUID, content_id: uuid.UUID
    ) -> tuple[ProgressResponse | None, Course | None, int]:
        """Get current progress, course, and lesson count."""
        current_progress = await progress_service.get_single_progress(user_id, content_id)

        # Get course for validation and defaults
        course_query = select(Course).where(Course.id == content_id, Course.user_id == user_id)
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
        self,
        metadata: ProgressMetadata,
        progress_data: ProgressUpdatePayload,
        completion_percentage: float,
        total_lessons: int,
    ) -> float:
        """Process lesson completion updates (stores a list of completed lesson ids)."""
        if "lesson_completed" not in progress_data:
            return completion_percentage

        lesson_id = progress_data.get("lesson_id")
        is_completed = progress_data["lesson_completed"]

        # Normalize existing value to a set
        completed_set = set(_completed_lesson_ids(metadata.get("completed_lessons")))

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

    async def _process_quiz_results(self, metadata: ProgressMetadata, progress_data: ProgressUpdatePayload) -> None:
        """Process quiz results updates."""
        if "quiz_results" not in progress_data:
            return

        quiz_results = progress_data["quiz_results"]
        lesson_id = progress_data.get("lesson_id")

        if isinstance(lesson_id, str) and isinstance(quiz_results, dict):
            quiz_results = cast("dict[str, object]", quiz_results)
            quiz_scores = metadata.get("quiz_scores", {})
            if not isinstance(quiz_scores, dict):
                quiz_scores = {}
            quiz_scores = cast("dict[str, object]", quiz_scores)
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

    def _process_settings_updates(self, metadata: ProgressMetadata, progress_data: ProgressUpdatePayload) -> None:
        """Process settings and preference updates."""
        # Update current lesson if provided
        if "current_lesson" in progress_data:
            metadata["current_lesson"] = progress_data["current_lesson"]

        # Update course settings/preferences
        if "pacing_preference" in progress_data:
            metadata["pacing_preference"] = progress_data["pacing_preference"]

    def _update_concept_review_stats(self, metadata: ProgressMetadata, progress_data: ProgressUpdatePayload) -> None:
        """Merge per-concept review telemetry into metadata."""
        incoming = progress_data.get("concept_review_stats")
        if not incoming:
            return

        if not isinstance(incoming, dict):
            return

        existing = metadata.get("concept_review_stats") or {}
        if not isinstance(existing, dict):
            existing = {}
        existing = cast("dict[str, object]", existing)
        for concept_id, concept_payload in incoming.items():
            if not isinstance(concept_payload, dict):
                continue
            concept_payload = cast("dict[str, object]", concept_payload)
            current_stats = existing.get(str(concept_id), {})
            if not isinstance(current_stats, dict):
                current_stats = {}
            current_stats = cast("dict[str, object]", current_stats)
            rating_counts = current_stats.get("ratingCounts", {"1": 0, "2": 0, "3": 0, "4": 0})
            if not isinstance(rating_counts, dict):
                rating_counts = {"1": 0, "2": 0, "3": 0, "4": 0}
            rating_counts = cast("dict[str, object]", rating_counts)
            incoming_rating_counts = concept_payload.get("ratingCounts", {})
            if not isinstance(incoming_rating_counts, dict):
                incoming_rating_counts = {}
            incoming_rating_counts = cast("dict[str, object]", incoming_rating_counts)
            for rating_key, count in incoming_rating_counts.items():
                rating_counts[rating_key] = _int_value(rating_counts.get(rating_key, 0)) + _int_value(count)
            current_stats["ratingCounts"] = rating_counts

            current_stats["totalDurationMs"] = _int_value(current_stats.get("totalDurationMs", 0)) + _int_value(
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

            existing[str(concept_id)] = current_stats

        metadata["concept_review_stats"] = existing

    def _update_recent_review_metadata(self, metadata: ProgressMetadata, progress_data: ProgressUpdatePayload) -> None:
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

    def _format_progress_response(
        self, updated: ProgressResponse, metadata: ProgressMetadata, total_lessons: int, _course: Course
    ) -> CourseProgressPayload:
        """Format the progress response."""
        completed_lessons = _completed_lesson_ids(metadata.get("completed_lessons"))

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
        return min(round(percentage, 2), 100.0)

    def _update_learning_patterns(  # noqa: PLR0912, PLR0915
        self, metadata: ProgressMetadata, _lesson_id: str, quiz_results: dict[str, object]
    ) -> None:
        """Update learning patterns based on quiz performance."""
        learning_patterns = metadata.get("learning_patterns", {})
        if not isinstance(learning_patterns, dict):
            learning_patterns = {}
        learning_patterns = cast("dict[str, object]", learning_patterns)

        # Analyze concept performance
        concepts = quiz_results.get("concepts", {})
        if not isinstance(concepts, dict):
            concepts = {}
        concepts = cast("dict[str, object]", concepts)
        total_score = quiz_results.get("total_score", 0)
        time_spent = quiz_results.get("time_spent", 0)
        numeric_score = float(total_score) if isinstance(total_score, str | int | float) else 0.0
        numeric_time_spent = float(time_spent) if isinstance(time_spent, str | int | float) else 0.0

        # Update concept strengths/weaknesses
        for concept, score in concepts.items():
            if concept not in learning_patterns:
                learning_patterns[concept] = {"scores": [], "avg_score": 0}
            pattern = learning_patterns[concept]
            if not isinstance(pattern, dict):
                pattern = {"scores": [], "avg_score": 0}
                learning_patterns[concept] = pattern
            pattern = cast("dict[str, object]", pattern)
            scores = pattern.get("scores", [])
            if not isinstance(scores, list):
                scores = []
            scores = cast("list[object]", scores)
            scores.append(score)

            # Keep only last 5 scores to track recent performance
            if len(scores) > 5:
                scores = scores[-5:]
            pattern["scores"] = scores

            numeric_scores = [float(item) for item in scores if isinstance(item, str | int | float)]
            pattern["avg_score"] = sum(numeric_scores) / len(numeric_scores) if numeric_scores else 0.0

        # Track overall performance trends
        if "overall_performance" not in learning_patterns:
            learning_patterns["overall_performance"] = {"scores": [], "time_efficiency": []}
        overall = learning_patterns["overall_performance"]
        if not isinstance(overall, dict):
            overall = {"scores": [], "time_efficiency": []}
            learning_patterns["overall_performance"] = overall
        overall = cast("dict[str, object]", overall)

        overall_scores = overall.get("scores", [])
        if not isinstance(overall_scores, list):
            overall_scores = []
        overall_scores = cast("list[object]", overall_scores)
        overall_scores.append(numeric_score)
        overall["scores"] = overall_scores
        if numeric_time_spent > 0:
            efficiency = numeric_score / (numeric_time_spent / 60)  # Score per minute
            time_efficiency = overall.get("time_efficiency", [])
            if not isinstance(time_efficiency, list):
                time_efficiency = []
            time_efficiency = cast("list[object]", time_efficiency)
            time_efficiency.append(efficiency)
            overall["time_efficiency"] = time_efficiency

        # Keep only recent data
        for key in ["scores", "time_efficiency"]:
            values = overall.get(key, [])
            if isinstance(values, list) and len(values) > 10:
                overall[key] = values[-10:]

        metadata["learning_patterns"] = learning_patterns
