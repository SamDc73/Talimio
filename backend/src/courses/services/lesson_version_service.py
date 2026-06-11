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

    async def select_current_version(self, *, lesson: Lesson, version: LessonVersion) -> LessonVersion:
        """Promote one existing version as the current lesson revision."""
        if version.lesson_id != lesson.id:
            raise NotFoundError(message="Lesson version not found", feature_area="courses")

        lesson.current_version_id = version.id
        lesson.content = version.content
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return version

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
                lesson_content = lesson.content or ""
                version_content = current_version.content or ""

                if not version_content and lesson_content:
                    current_version.content = lesson_content
                    await self.session.flush()
                    version_content = lesson_content

                if lesson.content != version_content:
                    lesson.content = version_content
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

        lesson_content = lesson.content or ""
        if not (latest_version.content or "") and lesson_content:
            latest_version.content = lesson_content
            await self.session.flush()

        return await self.select_current_version(lesson=lesson, version=latest_version)

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

    async def get_or_create_pending_initial_version(self, *, lesson: Lesson) -> LessonVersion:
        """Return the lesson's existing version, or create an empty 1.0 placeholder to be filled by a job.

        The placeholder carries ``generation_status='generating'`` and empty content;
        the generation job fills its content and flips the status to ``ready``.
        """
        latest_version = await self.session.scalar(
            select(LessonVersion)
            .where(LessonVersion.lesson_id == lesson.id)
            .order_by(LessonVersion.major_version.desc(), LessonVersion.minor_version.desc(), LessonVersion.created_at.desc())
            .limit(1)
        )
        if latest_version is not None:
            return latest_version

        pending_version = LessonVersion(
            lesson_id=lesson.id,
            major_version=1,
            minor_version=0,
            version_kind="first_pass",
            content="",
            generation_status="generating",
            generation_metadata={
                "source": "initial_generation",
                "source_reason": "First pass for this concept.",
            },
        )
        self.session.add(pending_version)
        await self.session.flush()
        lesson.current_version_id = pending_version.id
        lesson.updated_at = datetime.now(UTC)
        await self.session.flush()
        return pending_version

    async def create_pending_next_pass_version(
        self,
        *,
        lesson: Lesson,
        source_version: LessonVersion,
        source_reason: str,
    ) -> LessonVersion:
        """Create an empty next major pass row for a job to fill, without promoting it yet."""
        latest_version = await self.ensure_current_version(lesson=lesson)
        next_major = max(latest_version.major_version, source_version.major_version) + 1
        pending_version = LessonVersion(
            lesson_id=lesson.id,
            major_version=next_major,
            minor_version=0,
            version_kind="revisit_pass",
            content="",
            generation_status="generating",
            generation_metadata={
                "source": "adaptive_revisit",
                "source_version_id": str(source_version.id),
                "source_reason": source_reason,
            },
        )
        self.session.add(pending_version)
        await self.session.flush()
        return pending_version

    async def create_pending_regenerated_version(
        self,
        *,
        lesson: Lesson,
        critique_text: str,
    ) -> LessonVersion:
        """Create an empty minor regeneration row for a job to fill, without promoting it yet."""
        current_version = await self.ensure_current_version(lesson=lesson)
        pending_version = LessonVersion(
            lesson_id=lesson.id,
            major_version=current_version.major_version,
            minor_version=current_version.minor_version + 1,
            version_kind="regeneration",
            content="",
            generation_status="generating",
            generation_metadata={
                "source": "regenerate",
                "critique_text": critique_text,
                "source_version_id": str(current_version.id),
                "source_reason": critique_text[:160],
            },
        )
        self.session.add(pending_version)
        await self.session.flush()
        return pending_version

    async def fill_and_promote_version(self, *, lesson: Lesson, version: LessonVersion, content: str) -> LessonVersion:
        """Write generated content into a pending version, mark it ready, and promote it as current."""
        version.content = content
        version.generation_status = "ready"
        version.generation_error = None
        await self.session.flush()
        return await self.select_current_version(lesson=lesson, version=version)

    async def mark_version_failed(self, *, version: LessonVersion, error: str) -> None:
        """Flag a pending version as failed so reads stop polling and surface the error."""
        version.generation_status = "failed"
        version.generation_error = error[:2000]
        await self.session.flush()
