"""Service for handling progress operations."""

import logging
from typing import cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

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

        # Execute query based on session type
        if self._is_async:
            async_session = cast("AsyncSession", self._session)
            result = await async_session.execute(query)
        else:
            sync_session = cast("Session", self._session)
            result = sync_session.execute(query)

        progress = result.scalars().first()

        if progress:
            # Update existing record
            progress.status = data.status

            # Commit changes based on session type
            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                await async_session.commit()
                await async_session.refresh(progress)
            else:
                sync_session = cast("Session", self._session)
                sync_session.commit()
                sync_session.refresh(progress)

            return progress

        # Get the node to determine the roadmap_id
        try:
            # Try to convert lesson_id to UUID
            node_id = UUID(lesson_id)

            # Query the node to get its roadmap_id
            node_query = select(Node).where(Node.id == node_id)

            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                node_result = await async_session.execute(node_query)
            else:
                sync_session = cast("Session", self._session)
                node_result = sync_session.execute(node_query)

            node = node_result.scalar_one_or_none()

            # Use roadmap_id if node exists, otherwise use lesson_id
            course_id = str(node.roadmap_id) if node else lesson_id

        except (ValueError, TypeError):
            # If lesson_id is not a valid UUID, use it as the course_id
            course_id = lesson_id

        # Create new record
        progress = Progress(
            lesson_id=lesson_id,
            course_id=course_id,
            status=data.status,
        )
        self._session.add(progress)

        # Commit changes based on session type
        if self._is_async:
            async_session = cast("AsyncSession", self._session)
            await async_session.commit()
            await async_session.refresh(progress)
        else:
            sync_session = cast("Session", self._session)
            sync_session.commit()
            sync_session.refresh(progress)

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

            # Execute query based on session type
            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                total_nodes_result = await async_session.execute(total_nodes_query)
            else:
                sync_session = cast("Session", self._session)
                total_nodes_result = sync_session.execute(total_nodes_query)

            total_lessons = total_nodes_result.scalar() or 0

            if total_lessons == 0:
                # No lessons found for this course
                return 0, 0, 0

        except (ValueError, TypeError):
            # If course_id is not a valid UUID, fall back to counting progress records
            total_query = select(func.count()).select_from(Progress).where(Progress.course_id == course_id)

            # Execute query based on session type
            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                total_result = await async_session.execute(total_query)
            else:
                sync_session = cast("Session", self._session)
                total_result = sync_session.execute(total_query)

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

        # Execute query based on session type
        if self._is_async:
            async_session = cast("AsyncSession", self._session)
            completed_result = await async_session.execute(completed_query)
        else:
            sync_session = cast("Session", self._session)
            completed_result = sync_session.execute(completed_query)

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

            # Execute query based on session type
            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                nodes_result = await async_session.execute(nodes_query)
            else:
                sync_session = cast("Session", self._session)
                nodes_result = sync_session.execute(nodes_query)

            nodes = nodes_result.scalars().all()

            if not nodes:
                # No nodes found for this course
                return []

            # Get all progress records for this course
            progress_query = select(Progress).where(Progress.course_id == course_id)

            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                progress_result = await async_session.execute(progress_query)
            else:
                sync_session = cast("Session", self._session)
                progress_result = sync_session.execute(progress_query)

            progress_records = progress_result.scalars().all()

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

            # Execute query based on session type
            if self._is_async:
                async_session = cast("AsyncSession", self._session)
                result = await async_session.execute(query)
            else:
                sync_session = cast("Session", self._session)
                result = sync_session.execute(query)

            progress_records = result.scalars().all()

            return [
                LessonStatus(
                    id=str(record.lesson_id),
                    status=str(record.status),
                )
                for record in progress_records
            ]
