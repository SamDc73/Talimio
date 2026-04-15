import logging
import uuid
from typing import Any

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictError, NotFoundError, ValidationError
from src.highlights.interfaces import HighlightInterface
from src.highlights.models import Highlight
from src.highlights.schemas import HighlightResponse
from src.highlights.validation import validate_highlight_data
from src.videos.models import Video
from src.videos.service import VideoNotFoundError


logger = logging.getLogger(__name__)


class VideoHighlightService(HighlightInterface):
    """Service for managing highlights for videos, implementing the HighlightInterface contract."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize the video highlight service."""
        self.session = session

    async def create_highlight(
        self,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
        highlight_data: dict[str, Any],
    ) -> HighlightResponse:
        """Create a new highlight for a video."""
        await self._verify_video_ownership(content_id, user_id)

        try:
            validated_data = validate_highlight_data(highlight_data, _content_type="video")
            logger.debug(
                "Validated highlight data for video %s: type=%s",
                content_id,
                validated_data.get("_validation_type"),
            )
        except PydanticValidationError as error:
            logger.warning("Invalid highlight data for video %s: %s", content_id, error)
            message = f"Invalid highlight data: {error!s}"
            raise ValidationError(message, feature_area="videos") from error

        highlight = Highlight(
            user_id=user_id,
            content_type="video",
            content_id=content_id,
            highlight_data=validated_data,
        )

        try:
            self.session.add(highlight)
            await self.session.flush()
            await self.session.refresh(highlight)
        except IntegrityError as error:
            logger.warning("Conflict creating video highlight for video %s: %s", content_id, error)
            message = "Invalid highlight data or duplicate entry"
            raise ConflictError(message, feature_area="videos") from error

        return HighlightResponse.model_validate(highlight)

    async def get_highlights(
        self,
        content_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[HighlightResponse]:
        """Get all highlights for a video."""
        await self._verify_video_ownership(content_id, user_id)

        query = (
            select(Highlight)
            .where(
                and_(
                    Highlight.user_id == user_id,
                    Highlight.content_type == "video",
                    Highlight.content_id == content_id,
                )
            )
            .order_by(Highlight.created_at.desc())
        )

        result = await self.session.execute(query)
        highlights = result.scalars().all()

        return [HighlightResponse.model_validate(highlight) for highlight in highlights]

    async def get_highlight(
        self,
        highlight_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> HighlightResponse:
        """Get a specific highlight with ownership validation."""
        query = select(Highlight).where(and_(Highlight.id == highlight_id, Highlight.user_id == user_id))

        result = await self.session.execute(query)
        highlight = result.scalar_one_or_none()

        if not highlight:
            raise NotFoundError(message=f"Highlight {highlight_id} not found", feature_area="videos")

        return HighlightResponse.model_validate(highlight)

    async def update_highlight(
        self,
        highlight_id: uuid.UUID,
        user_id: uuid.UUID,
        highlight_data: dict[str, Any],
    ) -> HighlightResponse:
        """Update a highlight with ownership validation."""
        query = select(Highlight).where(and_(Highlight.id == highlight_id, Highlight.user_id == user_id))

        result = await self.session.execute(query)
        highlight = result.scalar_one_or_none()

        if not highlight:
            raise NotFoundError(message=f"Highlight {highlight_id} not found", feature_area="videos")

        try:
            validated_data = validate_highlight_data(highlight_data, _content_type="video")
            logger.debug(
                "Validated highlight data for update %s: type=%s",
                highlight_id,
                validated_data.get("_validation_type"),
            )
        except PydanticValidationError as error:
            logger.warning("Invalid highlight data for update %s: %s", highlight_id, error)
            message = f"Invalid highlight data: {error!s}"
            raise ValidationError(message, feature_area="videos") from error

        highlight.highlight_data = validated_data
        await self.session.flush()
        await self.session.refresh(highlight)

        return HighlightResponse.model_validate(highlight)

    async def delete_highlight(
        self,
        highlight_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> None:
        """Delete a highlight with ownership validation."""
        stmt = delete(Highlight).where(and_(Highlight.id == highlight_id, Highlight.user_id == user_id))
        result = await self.session.execute(stmt)
        await self.session.flush()

        affected = getattr(result, "rowcount", 0) or 0
        if affected == 0:
            raise NotFoundError(message=f"Highlight {highlight_id} not found", feature_area="videos")

    async def _verify_video_ownership(self, video_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Verify that the user owns the video."""
        query = select(Video).where(and_(Video.id == video_id, Video.user_id == user_id))

        result = await self.session.execute(query)
        video = result.scalar_one_or_none()

        if not video:
            raise VideoNotFoundError(message=f"Video {video_id} not found or access denied")
