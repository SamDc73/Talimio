"""Service for handling progress operations."""

import logging
from typing import cast
from uuid import UUID

from sqlalchemy import Result, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeMeta, Session

from src.progress.models import Progress
from src.progress.schemas import LessonStatus, StatusUpdate
from src.roadmaps.models import Node


logger = logging.getLogger(__name__)


class ProgressService:
    """Service for handling progress operations."""

    def __init__(self, session: Session | AsyncSession) -> None:
        """Initialize the progress service.

        Args:
            session: Database session (can be sync or async)
        """
        self._session = session
        self._is_async = isinstance(session, AsyncSession)

    async def _execute_query(self, query: Select) -> Result:
        """Execute a query based on session type."""
        if self._is_async:
            async_session = cast("AsyncSession", self._session)
            return await async_session.execute(query)
        sync_session = cast("Session", self._session)
        return sync_session.execute(query)

    async def _commit_and_refresh(self, obj: DeclarativeMeta) -> None:
        """Commit changes and refresh object based on session type."""
        if self._is_async:
            async_session = cast("AsyncSession", self._session)
            await async_session.commit()
            await async_session.refresh(obj)
        else:
            sync_session = cast("Session", self._session)
            sync_session.commit()
            sync_session.refresh(obj)

    async def _get_course_id(self, lesson_id: str) -> str:
        """Get course ID from either Node table or existing Progress records."""
        try:
            # Try to get course_id from Node table
            node_id = UUID(lesson_id)
            node_query = select(Node).where(Node.id == node_id)
            node_result = await self._execute_query(node_query)
            node = node_result.scalar_one_or_none()

            if node:
                return str(node.roadmap_id)

            logger.warning(f"Node not found for lesson_id: {lesson_id}")
            return lesson_id

        except (ValueError, TypeError):
            # Try to get course_id from existing Progress records
            existing_query = select(Progress).limit(1)
            existing_result = await self._execute_query(existing_query)
            existing_progress = existing_result.scalar_one_or_none()

            if existing_progress:
                course_id = existing_progress.course_id
                logger.info(f"Using existing course_id: {course_id} for lesson_id: {lesson_id}")
                return course_id

            logger.info(f"No existing progress records, using lesson_id as course_id: {lesson_id}")
            return lesson_id

    async def update_lesson_status(self, lesson_id: str, data: StatusUpdate) -> Progress:
        """Update lesson status.

        Args:
            lesson_id: Lesson ID
            data: Status update data

        Returns
        -------
            Updated progress record

        Raises
        ------
            ResourceNotFoundError: If lesson not found
            ValidationError: If status is invalid
        """
        # Check if progress record exists
        query = select(Progress).where(Progress.lesson_id == lesson_id)
        result = await self._execute_query(query)
        progress = result.scalars().first()

        if progress:
            # Update existing record
            progress.status = data.status
            await self._commit_and_refresh(progress)
            return progress

        # Create new record
        course_id = await self._get_course_id(lesson_id)
        progress = Progress(
            lesson_id=lesson_id,
            course_id=course_id,
            status=data.status,
        )
        self._session.add(progress)
        await self._commit_and_refresh(progress)

        return progress

    async def get_course_progress(self, course_id: str) -> tuple[int, int, int]:
        """Get course progress.

        Args:
            course_id: Course ID

        Returns
        -------
            Tuple of (total_lessons, completed_lessons, progress_percentage)

        Raises
        ------
            ResourceNotFoundError: If course not found
        """
        try:
            # Try to convert course_id to UUID for querying nodes
            roadmap_id = UUID(course_id)

            # Get total lessons from the nodes table
            total_nodes_query = select(func.count()).select_from(Node).where(Node.roadmap_id == roadmap_id)

            total_nodes_result = await self._execute_query(total_nodes_query)

            total_lessons = total_nodes_result.scalar() or 0

            if total_lessons == 0:
                # No lessons found for this course
                return 0, 0, 0

        except (ValueError, TypeError):
            # If course_id is not a valid UUID, fall back to counting progress records
            total_query = select(func.count()).select_from(Progress).where(Progress.course_id == course_id)

            total_result = await self._execute_query(total_query)

            total_lessons = total_result.scalar() or 0

            if total_lessons == 0:
                # No lessons found for this course
                return 0, 0, 0

        # Get completed lessons
        completed_query = (
            select(func.count())
            .select_from(Progress)
            .where(
                Progress.course_id == course_id,
                Progress.status == "done",
            )
        )

        completed_result = await self._execute_query(completed_query)

        completed_lessons = completed_result.scalar() or 0

        # Calculate percentage
        progress_percentage = int((completed_lessons / total_lessons) * 100) if total_lessons > 0 else 0

        return total_lessons, completed_lessons, progress_percentage

    async def get_lesson_statuses(self, course_id: str) -> list[LessonStatus]:
        """Get lesson statuses for a course.

        Args:
            course_id: Course ID

        Returns
        -------
            List of lesson statuses

        Raises
        ------
            ResourceNotFoundError: If course not found
        """
        try:
            # Try to convert course_id to UUID for querying nodes
            roadmap_id = UUID(course_id)

            # Get all nodes for this roadmap
            nodes_query = select(Node).where(Node.roadmap_id == roadmap_id)

            nodes_result = await self._execute_query(nodes_query)

            nodes = nodes_result.scalars().all()

            if not nodes:
                # No nodes found for this course
                return []

            # Get all progress records for this course
            # We need to check both by course_id and by lesson_id to catch all possible records
            progress_query = select(Progress).where(
                (Progress.course_id == course_id) | (Progress.lesson_id.in_([str(node.id) for node in nodes])),
            )

            progress_result = await self._execute_query(progress_query)

            progress_records = progress_result.scalars().all()

            # Log the found progress records for debugging
            logger.debug(f"Found {len(progress_records)} progress records for course_id: {course_id}")

            # Create a map of lesson_id to status
            progress_map = {str(record.lesson_id): record.status for record in progress_records}

            # Create a list of lesson statuses for all nodes
            lesson_statuses = []
            for node in nodes:
                node_id_str = str(node.id)
                lesson_statuses.append(
                    LessonStatus(
                        id=node_id_str,
                        status=progress_map.get(node_id_str, "not_started"),
                    ),
                )

            return lesson_statuses

        except (ValueError, TypeError):
            # If course_id is not a valid UUID, fall back to just returning progress records
            query = select(Progress).where(Progress.course_id == course_id)

            result = await self._execute_query(query)

            progress_records = result.scalars().all()

            return [
                LessonStatus(
                    id=str(record.lesson_id),
                    status=str(record.status),
                )
                for record in progress_records
            ]
