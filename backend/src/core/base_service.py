"""Base service class for all content types with shared behavior."""

import logging
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from src.ai.ai_service import AIService
from src.tagging.service import TaggingService


logger = logging.getLogger(__name__)


class BaseContentService(ABC):
    """Shared behavior for all content types."""

    def __init__(self) -> None:
        # Don't initialize services here - they'll be created as needed with proper session
        self.ai_service = AIService()

    async def create_content(self, data: dict, user_id: UUID) -> Any:
        """Create content with standard processing pipeline."""
        # 1. Create the content
        content = await self._do_create(data, user_id)

        # 2. Always update progress (direct call)
        await self._update_progress(content.id, user_id, status="created")

        # 3. Always process tags (direct call)
        if data.get("tags"):
            await self._process_tags(content.id, user_id, data["tags"])

        # 4. Queue for AI processing if needed
        if self._needs_ai_processing(content):
            await self._queue_ai_processing(content.id, user_id)

        return content

    async def update_content(self, content_id: UUID, data: dict, user_id: UUID) -> Any:
        """Update content with standard processing pipeline."""
        # 1. Update the content
        content = await self._do_update(content_id, data, user_id)

        # 2. Process tags if updated
        if "tags" in data:
            await self._process_tags(content_id, user_id, data["tags"])

        # 3. Queue for AI reprocessing if needed
        if self._needs_ai_reprocessing(content, data):
            await self._queue_ai_processing(content_id, user_id)

        return content

    async def delete_content(self, content_id: UUID, user_id: UUID) -> bool:
        """Delete content with cleanup."""
        # 1. Delete associated data (progress, tags)
        await self._cleanup_associated_data(content_id, user_id)

        # 2. Delete the content
        return await self._do_delete(content_id, user_id)

    @abstractmethod
    async def _do_create(self, data: dict, user_id: UUID) -> Any:
        """Each module implements this to create their specific content."""

    @abstractmethod
    async def _do_update(self, content_id: UUID, data: dict, user_id: UUID) -> Any:
        """Each module implements this to update their specific content."""

    @abstractmethod
    async def _do_delete(self, content_id: UUID, user_id: UUID) -> bool:
        """Each module implements this to delete their specific content."""

    async def _update_progress(self, content_id: UUID, user_id: UUID, status: str) -> None:
        """Update progress tracking for content."""
        _ = user_id
        try:
            # Default implementation - modules can override
            logger.info(f"Progress updated for {content_id}: {status}")
        except Exception as e:
            logger.exception(f"Failed to update progress: {e}")

    async def _process_tags(self, content_id: UUID, user_id: UUID, tags: list[str]) -> None:
        """Process tags for content."""
        try:
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                tagging_service = TaggingService(session)
                content_type = self._get_content_type()
                await tagging_service.process_tags(
                    content_type=content_type,
                    content_id=str(content_id),
                    user_id=user_id,
                    tags=tags
                )
        except Exception as e:
            logger.exception(f"Failed to process tags: {e}")

    def _needs_ai_processing(self, content: Any) -> bool:
        """Check if content needs AI processing after creation."""
        _ = content
        # Default: no AI processing needed
        # Modules can override for their specific logic
        return False

    def _needs_ai_reprocessing(self, content: Any, updated_data: dict) -> bool:
        """Check if content needs AI reprocessing after update."""
        _ = content
        _ = updated_data
        # Default: no reprocessing needed
        # Modules can override
        return False

    async def _queue_ai_processing(self, content_id: UUID, user_id: UUID) -> None:
        """Queue content for AI processing."""
        try:
            content_type = self._get_content_type()
            # Use the AI service for processing
            await self.ai_service.queue_processing(
                content_type=content_type,
                content_id=str(content_id),
                user_id=user_id
            )
        except Exception as e:
            logger.exception(f"Failed to queue AI processing: {e}")

    async def _cleanup_associated_data(self, content_id: UUID, user_id: UUID) -> None:
        """Clean up associated data before deletion."""
        try:
            from src.database.session import async_session_maker

            async with async_session_maker() as session:
                # Clean up tags
                tagging_service = TaggingService(session)
                content_type = self._get_content_type()
                await tagging_service.remove_all_tags(
                    content_type=content_type,
                    content_id=str(content_id),
                    user_id=user_id
                )
        except Exception as e:
            logger.exception(f"Failed to cleanup associated data: {e}")

    @abstractmethod
    def _get_content_type(self) -> str:
        """Return the content type for this service."""
