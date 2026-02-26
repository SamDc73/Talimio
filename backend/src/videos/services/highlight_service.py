
import uuid

from sqlalchemy.ext.asyncio import AsyncSession


"""Video highlight service implementing the HighlightInterface contract."""

import logging
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import and_, delete, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from src.highlights.interfaces import HighlightInterface
from src.highlights.models import Highlight
from src.highlights.schemas import HighlightResponse
from src.highlights.validation import validate_highlight_data
from src.videos.models import Video


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
        except ValidationError as e:
            logger.warning("Invalid highlight data for video %s: %s", content_id, e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid highlight data: {e!s}") from e

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
        except IntegrityError as e:
            logger.exception("Integrity constraint violation creating video highlight: %s", e)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid highlight data or duplicate entry"
            ) from e
        except SQLAlchemyError as e:
            logger.exception("Database error creating video highlight: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred"
            ) from e
        except (AttributeError, RuntimeError, TypeError, ValueError) as e:
            logger.exception("Unexpected error creating video highlight: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred"
            ) from e

        logger.info("Created video highlight %s for video %s by user %s", highlight.id, content_id, user_id)
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

        logger.info("Retrieved %s highlights for video %s", len(highlights), content_id)
        return [HighlightResponse.model_validate(h) for h in highlights]

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Highlight {highlight_id} not found")

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
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Highlight {highlight_id} not found")

        try:
            validated_data = validate_highlight_data(highlight_data, _content_type="video")
            logger.debug(
                "Validated highlight data for update %s: type=%s",
                highlight_id,
                validated_data.get("_validation_type"),
            )
        except ValidationError as e:
            logger.warning("Invalid highlight data for update %s: %s", highlight_id, e)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid highlight data: {e!s}") from e

        highlight.highlight_data = validated_data

        try:
            await self.session.flush()
            await self.session.refresh(highlight)
        except SQLAlchemyError as e:
            logger.exception("Database error updating video highlight %s: %s", highlight_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred"
            ) from e
        except (AttributeError, RuntimeError, TypeError, ValueError) as e:
            logger.exception("Unexpected error updating video highlight %s: %s", highlight_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred"
            ) from e

        logger.info("Updated highlight %s", highlight_id)
        return HighlightResponse.model_validate(highlight)

    async def delete_highlight(
        self,
        highlight_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> bool:
        """Delete a highlight with ownership validation."""
        stmt = delete(Highlight).where(and_(Highlight.id == highlight_id, Highlight.user_id == user_id))

        try:
            result = await self.session.execute(stmt)
            await self.session.flush()
        except SQLAlchemyError as e:
            logger.exception("Database error deleting video highlight %s: %s", highlight_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Database error occurred"
            ) from e
        except (AttributeError, RuntimeError, TypeError, ValueError) as e:
            logger.exception("Unexpected error deleting video highlight %s: %s", highlight_id, e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An unexpected error occurred"
            ) from e

        affected = getattr(result, "rowcount", 0) or 0
        if affected == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Highlight {highlight_id} not found")

        logger.info("Deleted highlight %s", highlight_id)
        return True

    async def _verify_video_ownership(self, video_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """Verify that the user owns the video."""
        query = select(Video).where(and_(Video.id == video_id, Video.user_id == user_id))

        result = await self.session.execute(query)
        video = result.scalar_one_or_none()

        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=f"Video {video_id} not found or access denied"
            )
