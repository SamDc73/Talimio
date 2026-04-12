import re
from dataclasses import dataclass

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.courses.models import Course, LessonVersion, LessonVersionWindow


_WINDOW_HEADING_RE = re.compile(
    r"^##\s+Window\s+(\d+)\s*[:\-]\s*(.+?)(?:\s+\[(\d+)\s*min\])?\s*$",
    re.MULTILINE,
)
_FIRST_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class ParsedLessonWindow:
    """Window payload before persistence."""

    window_index: int
    title: str | None
    content: str
    estimated_minutes: int


class LessonWindowService:
    """Persist and parse version-scoped lesson windows."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def build_generation_context(self, *, course: Course) -> str:
        """Return high-level prompt guidance for model-chosen lesson windows."""
        adaptive_hint = (
            "Use the learner and course context to decide how much segmentation helps."
            if course.adaptive_enabled
            else "Use the lesson topic and surrounding course context to decide how much segmentation helps."
        )
        return (
            "## Lesson Windows\n"
            "Write the full lesson in one pass.\n"
            "Segment it into windows only when that improves pacing and clarity for this lesson.\n"
            "Let the lesson and learner context decide how many windows feel natural.\n"
            f"{adaptive_hint}\n"
            "Avoid over-segmentation.\n"
            "When you use windows, start each one with a level-2 heading in this exact format: `## Window 1: <short title> [5 min]`.\n"
            "Use `###` headings inside each window for subsections.\n"
            "Keep the lesson digestible and coherent.\n"
            "The final response must still be one coherent lesson body, not JSON and not separate lessons."
        )

    async def get_or_build_windows(self, *, lesson_version: LessonVersion) -> list[LessonVersionWindow]:
        """Return stored windows for a version, lazily creating them when absent."""
        existing_windows = (
            (
                await self.session.execute(
                    select(LessonVersionWindow)
                    .where(LessonVersionWindow.lesson_version_id == lesson_version.id)
                    .order_by(LessonVersionWindow.window_index.asc())
                )
            )
            .scalars()
            .all()
        )
        if existing_windows:
            return existing_windows

        parsed_windows = self.parse_windows(lesson_version.content)
        created_windows = [
            LessonVersionWindow(
                lesson_version_id=lesson_version.id,
                window_index=window.window_index,
                title=window.title,
                content=window.content,
                estimated_minutes=window.estimated_minutes,
            )
            for window in parsed_windows
        ]
        self.session.add_all(created_windows)
        await self.session.flush()
        return created_windows

    async def rebuild_windows(self, *, lesson_version: LessonVersion) -> list[LessonVersionWindow]:
        """Replace persisted windows after a version body changes."""
        await self.session.execute(
            delete(LessonVersionWindow).where(LessonVersionWindow.lesson_version_id == lesson_version.id)
        )
        await self.session.flush()
        return await self.get_or_build_windows(lesson_version=lesson_version)

    def parse_windows(self, content: str) -> list[ParsedLessonWindow]:
        """Parse one generated lesson body into window records."""
        if not content.strip():
            return [ParsedLessonWindow(window_index=0, title="Lesson", content="", estimated_minutes=1)]

        matches = list(_WINDOW_HEADING_RE.finditer(content))
        if not matches:
            return [self._build_single_window(content)]

        parsed_windows: list[ParsedLessonWindow] = []
        for index, match in enumerate(matches):
            next_match = matches[index + 1] if index + 1 < len(matches) else None
            body_start = match.end()
            body_end = next_match.start() if next_match is not None else len(content)
            body = content[body_start:body_end].strip()
            explicit_minutes = match.group(3)
            parsed_windows.append(
                ParsedLessonWindow(
                    window_index=index,
                    title=match.group(2).strip() or None,
                    content=body,
                    estimated_minutes=(
                        int(explicit_minutes)
                        if explicit_minutes is not None
                        else self._estimate_minutes(body)
                    ),
                )
            )
        return parsed_windows

    def _build_single_window(self, content: str) -> ParsedLessonWindow:
        heading_match = _FIRST_HEADING_RE.search(content)
        title = heading_match.group(1).strip() if heading_match is not None else "Lesson"
        return ParsedLessonWindow(
            window_index=0,
            title=title,
            content=content.strip(),
            estimated_minutes=self._estimate_minutes(content),
        )

    def _estimate_minutes(self, content: str) -> int:
        word_count = max(1, len(content.split()))
        return max(1, round(word_count / 170))
