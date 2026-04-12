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
                if lesson.content != current_version.content:
                    lesson.content = current_version.content
                    lesson.updated_at = datetime.now(UTC)
                    await self.session.flush()
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
                generation_metadata={},
            )
            self.session.add(latest_version)
            await self.session.flush()

        lesson.current_version_id = latest_version.id
        lesson.content = latest_version.content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return latest_version

    async def sync_current_version_from_lesson(self, *, lesson: Lesson) -> LessonVersion:
        """Keep the lesson content field as a compatibility mirror of the version row."""
        return await self.ensure_current_version(lesson=lesson)

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
        versions = (
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
        return list(versions)

    async def create_initial_version(self, *, lesson: Lesson, content: str) -> LessonVersion:
        """Create the first canonical version for a lesson whose content is being generated."""
        current_version = await self.session.scalar(
            select(LessonVersion)
            .where(LessonVersion.lesson_id == lesson.id)
            .order_by(LessonVersion.major_version.desc(), LessonVersion.minor_version.desc(), LessonVersion.created_at.desc())
            .limit(1)
        )
        if current_version is not None:
            lesson.current_version_id = current_version.id
            lesson.content = current_version.content
            lesson.updated_at = datetime.now(UTC)
            await self.session.flush()
            return current_version

        new_version = LessonVersion(
            lesson_id=lesson.id,
            major_version=1,
            minor_version=0,
            version_kind="first_pass",
            content=content,
            generation_metadata={
                "source": "initial_generation",
                "source_reason": "First pass for this concept.",
            },
        )
        self.session.add(new_version)
        await self.session.flush()

        lesson.current_version_id = new_version.id
        lesson.content = content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return new_version

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
            version_kind="regeneration",
            content=content,
            generation_metadata={
                "source": "regenerate",
                "critique_text": critique_text,
                "source_version_id": str(current_version.id),
                "source_reason": critique_text[:160],
            },
        )
        self.session.add(new_version)
        await self.session.flush()

        lesson.current_version_id = new_version.id
        lesson.content = content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return new_version

    async def create_adaptive_pass_version(
        self,
        *,
        lesson: Lesson,
        content: str,
        source_version: LessonVersion,
        source_reason: str,
    ) -> LessonVersion:
        """Create the next major lesson pass for an adaptive revisit."""
        latest_version = await self.ensure_current_version(lesson=lesson)
        next_major = max(latest_version.major_version, source_version.major_version) + 1
        new_version = LessonVersion(
            lesson_id=lesson.id,
            major_version=next_major,
            minor_version=0,
            version_kind="revisit_pass",
            content=content,
            generation_metadata={
                "source": "adaptive_revisit",
                "source_version_id": str(source_version.id),
                "source_reason": source_reason,
            },
        )
        self.session.add(new_version)
        await self.session.flush()

        lesson.current_version_id = new_version.id
        lesson.content = content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return new_version
