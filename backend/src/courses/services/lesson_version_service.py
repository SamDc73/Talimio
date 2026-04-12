import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Lesson, LessonVersion
from src.exceptions import NotFoundError


class LessonVersionService:
    """Manage stable lesson revisions while keeping lesson rows backward compatible."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def ensure_current_version(self, *, lesson: Lesson) -> LessonVersion:
        """Return the current version, backfilling 1.0 when the lesson has only flat content."""
        if lesson.current_version_id is not None:
            current_version = await self.session.scalar(
                select(LessonVersion).where(
                    LessonVersion.id == lesson.current_version_id,
                    LessonVersion.lesson_id == lesson.id,
                )
            )
            if current_version is not None:
                return current_version

        latest_version = await self.session.scalar(
            select(LessonVersion)
            .where(LessonVersion.lesson_id == lesson.id)
            .order_by(LessonVersion.major_version.desc(), LessonVersion.minor_version.desc(), LessonVersion.created_at.desc())
            .limit(1)
        )
        if latest_version is None:
            latest_version = LessonVersion(
                lesson_id=lesson.id,
                major_version=1,
                minor_version=0,
                version_kind="first_pass",
                content=lesson.content,
            )
            self.session.add(latest_version)
            await self.session.flush()

        lesson.current_version_id = latest_version.id
        lesson.content = latest_version.content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return latest_version

    async def sync_current_version_from_lesson(self, *, lesson: Lesson) -> LessonVersion:
        """Keep the current version row aligned with the compatibility content field."""
        current_version = await self.ensure_current_version(lesson=lesson)
        if current_version.content != lesson.content:
            current_version.content = lesson.content
            await self.session.flush()
        return current_version

    async def get_version(self, *, lesson: Lesson, version_id: uuid.UUID | None) -> LessonVersion:
        """Return the requested version or the current one when no version is specified."""
        current_version = await self.ensure_current_version(lesson=lesson)
        if version_id is None or version_id == current_version.id:
            return current_version

        requested_version = await self.session.scalar(
            select(LessonVersion).where(
                LessonVersion.id == version_id,
                LessonVersion.lesson_id == lesson.id,
            )
        )
        if requested_version is None:
            raise NotFoundError(message="Lesson version not found", feature_area="courses")
        return requested_version

    async def list_versions(self, *, lesson: Lesson) -> list[LessonVersion]:
        """Return all versions for one lesson from newest to oldest."""
        await self.ensure_current_version(lesson=lesson)
        return (
            (
                await self.session.execute(
                    select(LessonVersion)
                    .where(LessonVersion.lesson_id == lesson.id)
                    .order_by(
                        LessonVersion.major_version.desc(),
                        LessonVersion.minor_version.desc(),
                        LessonVersion.created_at.desc(),
                    )
                )
            )
            .scalars()
            .all()
        )

    async def create_regenerated_version(
        self,
        *,
        lesson: Lesson,
        content: str,
        critique_text: str,
    ) -> LessonVersion:
        """Create a new minor version and promote it as the current lesson revision."""
        current_version = await self.ensure_current_version(lesson=lesson)
        new_version = LessonVersion(
            lesson_id=lesson.id,
            major_version=current_version.major_version,
            minor_version=current_version.minor_version + 1,
            version_kind=current_version.version_kind,
            content=content,
            generation_metadata={"source": "regenerate", "critique_text": critique_text},
        )
        self.session.add(new_version)
        await self.session.flush()

        lesson.current_version_id = new_version.id
        lesson.content = content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return new_version
