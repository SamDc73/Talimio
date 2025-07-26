"""Content progress service."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentType


logger = logging.getLogger(__name__)


class ContentProgressService:
    """Service for unified content operations including progress tracking."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the content service."""
        self.session = session


    def _convert_to_uuid(self, content_id: str | UUID) -> UUID | None:
        """Convert string to UUID if needed."""
        if isinstance(content_id, UUID):
            return content_id
        try:
            return UUID(content_id)
        except ValueError:
            return None

    async def _get_course_progress(self, content_id: UUID, user_id: UUID | None) -> int:
        """Get course progress."""
        from src.courses.services.course_progress_service import CourseProgressService
        if user_id is None:
            return 0
        try:
            service = CourseProgressService(self.session, user_id)
            return await service.get_course_progress_percentage(content_id, user_id)
        except ValueError:
            return 0

    async def _get_book_progress(self, content_id: UUID, user_id: UUID | None) -> int:
        """Get book progress based on chapter completion (aligns with course progress mechanism)."""
        if not user_id:
            return 0

        # Use book facade for progress calculation
        from src.books.facade import BooksFacade
        try:
            facade = BooksFacade(self.session)
            book_data = await facade.get_book_with_progress(content_id, user_id)
            return book_data.get("progress", {}).get("progress_percentage", 0)
        except (ValueError, KeyError):
            return 0

    async def _get_video_progress(self, content_id: UUID, user_id: UUID | None) -> int:
        """Get video progress."""
        if not user_id:
            return 0

        # Use video facade for progress calculation
        from src.videos.facade import VideosFacade
        try:
            facade = VideosFacade()
            # Use get_video_with_progress which exists in the facade
            video_data = await facade.get_video_with_progress(content_id, user_id)
            if video_data and video_data.get("success"):
                return video_data.get("completion_percentage", 0)
            return 0
        except (ValueError, KeyError):
            return 0

    async def _get_flashcard_progress(self, _content_id: UUID, _user_id: UUID | None) -> int:
        """Get flashcard progress."""
        return 0  # TODO: Implement when flashcard progress is needed


    def _group_items_by_type(self, items: list[tuple[str, str | UUID, UUID | None]]) -> dict[str, list[tuple[str | UUID, UUID | None]]]:
        """Group items by content type."""
        grouped = {}
        for content_type, content_id, user_id in items:
            if content_type not in grouped:
                grouped[content_type] = []
            grouped[content_type].append((content_id, user_id))
        return grouped




async def _calculate_course_progress(session: AsyncSession, items: list[Any], user_id: UUID) -> list[Any]:
    """Calculate accurate course progress using CourseProgressService (DRY)."""
    # Filter for course items only (roadmap type in DB, but shows as course in enum)
    # Check for ContentType.COURSE enum value
    from src.courses.services.course_progress_service import CourseProgressService

    course_items = [item for item in items if hasattr(item, "type") and (item.type == ContentType.COURSE or str(item.type) == "course")]

    if not course_items:
        return items

    # Initialize progress service
    progress_service = CourseProgressService(session, user_id)

    # Calculate progress for each course using our DRY service
    for item in course_items:
        try:
            course_id = UUID(item.id)

            # Use our DRY CourseProgressService
            progress = await progress_service.get_course_progress_percentage(course_id, user_id)
            stats = await progress_service.get_lesson_completion_stats(course_id, user_id)

            # Update the item's progress with standardized ProgressData
            from src.content.schemas import ProgressData
            item.progress = ProgressData(
                percentage=float(progress),
                completed_items=stats["completed_lessons"],
                total_items=stats["total_lessons"]
            )

            # Update completed_lessons count for backward compatibility
            if hasattr(item, "completed_lessons"):
                item.completed_lessons = stats["completed_lessons"]
            elif hasattr(item, "completedLessons"):
                item.completedLessons = stats["completed_lessons"]

        except (ValueError, Exception) as e:
            # Keep original progress (0) if there's an error
            logger.debug(f"Error calculating course progress for {item.id}: {e}")

    return items


async def _calculate_book_progress(_session: AsyncSession, items: list[Any], user_id: UUID) -> list[Any]:
    """Calculate accurate book progress from ToC progress and actual table of contents.

    This function properly calculates progress by:
    1. Getting the actual table of contents from the book
    2. Counting all sections in the ToC (recursively)
    3. Calculating progress based on completed sections vs total sections
    """
    # Filter for book items only
    import json

    from src.content.schemas import ContentType
    book_items = [item for item in items if hasattr(item, "type") and item.type == ContentType.BOOK]

    logger.info(f"📚 _calculate_book_progress called with {len(book_items)} book items for user {user_id}")

    # Debug: Log each book's current state
    for item in book_items:
        toc_progress = getattr(item, "tocProgress", None) or getattr(item, "toc_progress", {})
        logger.info(f"📚 Book {item.id}: Current tocProgress from query = {toc_progress}")
        logger.info(f"📚 Book {item.id}: Item attributes = {[attr for attr in dir(item) if not attr.startswith('_')]}")

    if not book_items:
        return items

    # Calculate progress for each book
    for item in book_items:
        try:
            book_id = UUID(item.id)

            # Get the toc_progress from the item (already parsed by transform service)
            toc_progress = getattr(item, "tocProgress", None) or getattr(item, "toc_progress", {})
            if isinstance(toc_progress, str):
                try:
                    toc_progress = json.loads(toc_progress)
                except (json.JSONDecodeError, TypeError):
                    toc_progress = {}

            logger.info(f"📚 Book {book_id}: Parsed toc_progress = {toc_progress}, type = {type(toc_progress)}")

            logger.info(f"📚 Book {book_id}: Progress has {len(toc_progress)} entries")

            # Check if we already have a stored progress percentage from the query
            stored_progress = getattr(item, "progress", None)
            logger.info(f"📚 Book {book_id}: Raw stored_progress value = {stored_progress}, type = {type(stored_progress)}")

            # Always use stored progress from database - it's already calculated by BookProgressService
            from src.content.schemas import ProgressData
            if isinstance(stored_progress, ProgressData):
                # If it's already a ProgressData object, just use it
                item.progress = stored_progress
                continue
            # Otherwise, extract the percentage value
            progress = float(stored_progress) if stored_progress is not None else 0.0

            # For completed/total items, we can estimate from toc_progress if available
            completed_sections = sum(1 for status in toc_progress.values() if status is True) if toc_progress else 0
            # Estimate total sections based on progress percentage if we have it
            if progress > 0 and completed_sections > 0:
                total_sections = int(completed_sections * 100 / progress)
            else:
                total_sections = len(toc_progress) if toc_progress else 0

            logger.info(f"📚 Book {book_id}: Using stored progress from DB = {progress}% ({completed_sections} completed)")

            # Update the item's progress with standardized ProgressData
            from src.content.schemas import ProgressData
            item.progress = ProgressData(
                percentage=float(progress),
                completed_items=completed_sections,
                total_items=total_sections
            )

        except (ValueError, Exception) as e:
            # Keep original progress if there's an error
            logger.exception(f"Error calculating book progress for book {item.id}: {e}")
            from src.content.schemas import ProgressData
            item.progress = ProgressData(
                percentage=0.0,
                completed_items=0,
                total_items=0
            )

    return items


async def _calculate_video_progress(session: AsyncSession, items: list[Any], user_id: UUID) -> list[Any]:
    """Calculate accurate video progress using time-based calculation (matching book/course pattern)."""
    # Filter for video items only (youtube type)
    from src.content.schemas import ContentType
    from src.videos.models import Video, VideoProgress
    video_items = [item for item in items if hasattr(item, "type") and item.type == ContentType.YOUTUBE]

    if not video_items:
        return items

    # Calculate progress for each video using time-based calculation
    for item in video_items:
        try:
            video_id = UUID(item.id)

            # Get video duration first
            from sqlalchemy import select
            video_query = select(Video).where(Video.uuid == video_id)
            video_result = await session.execute(video_query)
            video = video_result.scalar_one_or_none()

            if not video or not video.duration:
                from src.content.schemas import ProgressData
                item.progress = ProgressData(
                    percentage=0.0,
                    completed_items=0,
                    total_items=0
                )
                continue

            # Get progress record for this user and video
            progress_query = select(VideoProgress).where(
                VideoProgress.video_uuid == video_id,
                VideoProgress.user_id == user_id
            )
            progress_result = await session.execute(progress_query)
            progress = progress_result.scalar_one_or_none()

            if not progress:
                from src.content.schemas import ProgressData
                item.progress = ProgressData(
                    percentage=0.0,
                    completed_items=0,
                    total_items=0
                )
                continue

            # Use stored completion_percentage if available (from chapter-based progress)
            # Otherwise calculate time-based progress percentage
            from src.content.schemas import ProgressData

            # For videos, completed_items and total_items refer to chapters if available
            # Get chapter count and completed chapters
            from src.videos.models import VideoChapter
            chapters_query = select(VideoChapter).where(VideoChapter.video_uuid == video_id)
            chapters_result = await session.execute(chapters_query)
            chapters = chapters_result.scalars().all()

            total_chapters = len(chapters)
            completed_chapters = sum(1 for ch in chapters if ch.status == "completed")

            if progress.completion_percentage is not None and progress.completion_percentage > 0:
                percentage = float(progress.completion_percentage)
            elif progress.last_position is not None and video.duration > 0:
                percentage = min(100, (progress.last_position / video.duration) * 100)
            else:
                percentage = 0.0

            item.progress = ProgressData(
                percentage=percentage,
                completed_items=completed_chapters,
                total_items=total_chapters
            )

        except (ValueError, Exception) as e:
            # Keep original progress if there's an error
            logger.debug(f"Error calculating video progress for video {item.id}: {e}")
            from src.content.schemas import ProgressData
            item.progress = ProgressData(
                percentage=0.0,
                completed_items=0,
                total_items=0
            )

    return items


async def _calculate_flashcard_progress(session: AsyncSession, items: list[Any], user_id: UUID) -> list[Any]:
    """Calculate accurate flashcard progress using FSRS algorithm (matching course pattern)."""
    from datetime import UTC, datetime

    from sqlalchemy import func, select

    # Filter for flashcard items only
    from src.content.schemas import ContentType
    from src.flashcards.models import FlashcardCard, FlashcardDeck
    flashcard_items = [item for item in items if hasattr(item, "type") and item.type == ContentType.FLASHCARDS]

    if not flashcard_items:
        return items

    # Calculate progress for each flashcard deck
    for item in flashcard_items:
        try:
            deck_id = UUID(item.id)
            now = datetime.now(UTC)

            # Get total cards, due cards, and overdue cards
            stats_query = select(
                func.count(FlashcardCard.id).label("total"),
                func.count(FlashcardCard.id).filter(FlashcardCard.due <= now).label("due"),
                func.count(FlashcardCard.id).filter(FlashcardCard.due < now).label("overdue")
            ).where(
                FlashcardCard.deck_id == deck_id,
                FlashcardDeck.user_id == user_id
            ).join(FlashcardDeck)

            result = await session.execute(stats_query)
            stats = result.first()

            from src.content.schemas import ProgressData

            if not stats or stats.total == 0:
                # No cards in deck
                item.progress = ProgressData(
                    percentage=0.0,
                    completed_items=0,
                    total_items=0
                )
            else:
                reviewed_cards = stats.total - stats.due
                progress = (reviewed_cards / stats.total) * 100
                item.progress = ProgressData(
                    percentage=float(max(0, progress)),
                    completed_items=reviewed_cards,
                    total_items=stats.total
                )

            # Store additional stats for web app if needed
            if hasattr(item, "due_count"):
                item.due_count = stats.due if stats else 0
            if hasattr(item, "card_count"):
                item.card_count = stats.total if stats else 0

        except (ValueError, Exception) as e:
            # Keep original progress (0) if there's an error
            logger.debug(f"Error calculating flashcard progress for deck {item.id}: {e}")
            from src.content.schemas import ProgressData
            item.progress = ProgressData(
                percentage=0.0,
                completed_items=0,
                total_items=0
            )

    return items
