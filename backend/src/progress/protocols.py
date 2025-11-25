"""Progress tracking protocols and base classes.

This module defines the contracts for progress tracking across different content types.
"""

from abc import ABC, abstractmethod
from typing import Any, Protocol
from uuid import UUID


class ProgressTracker(Protocol):
    """Protocol for tracking content progress across different content types."""

    async def get_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get progress data for specific content and user."""
        ...

    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update progress data for specific content and user."""
        ...

    async def calculate_completion_percentage(self, content_id: UUID, user_id: UUID) -> float:
        """Calculate completion percentage (0.0 to 100.0)."""
        ...


class ContentFacade(ABC):
    """Base class for content module facades.

    Note: Each module should implement its own facade independently.
    This base class is provided for type hints and consistency only.
    """

    @abstractmethod
    async def get_content_with_progress(self, content_id: UUID, user_id: UUID) -> dict[str, Any]:
        """Get content with progress information."""

    @abstractmethod
    async def create_content(self, content_data: dict[str, Any], user_id: UUID) -> dict[str, Any]:
        """Create new content."""

    @abstractmethod
    async def update_progress(self, content_id: UUID, user_id: UUID, progress_data: dict[str, Any]) -> dict[str, Any]:
        """Update content progress."""

    @abstractmethod
    async def delete_content(self, content_id: UUID, user_id: UUID) -> bool:
        """Delete content."""
