"""
Service Contracts and Interfaces.

Defines protocols and interfaces for module boundaries.
These contracts prevent coupling while enabling clean communication between modules.
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


class ContentProcessor(Protocol):
    """Protocol for processing different types of content."""

    async def process_content(
        self, content_id: UUID, content_type: str, processing_options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Process content for AI/RAG/search indexing."""
        ...

    async def extract_metadata(self, content_id: UUID) -> dict[str, Any]:
        """Extract metadata from content."""
        ...

    async def generate_summary(self, content_id: UUID) -> str:
        """Generate AI summary of content."""
        ...


class UserResolver(Protocol):
    """Protocol for resolving user context and permissions."""

    async def get_current_user_id(self, request_context: Any) -> UUID:
        """Resolve current user ID from request context."""
        ...

    async def has_permission(self, user_id: UUID, resource_id: UUID, action: str) -> bool:
        """Check if user has permission for specific action on resource."""
        ...

    async def get_user_preferences(self, user_id: UUID) -> dict[str, Any]:
        """Get user preferences and settings."""
        ...


class ContentFacade(ABC):
    """Base class for content module facades."""

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


class EventPublisher(Protocol):
    """Protocol for publishing events to decouple modules."""

    async def publish(self, event_type: str, event_data: dict[str, Any], delay_seconds: int | None = None) -> bool:
        """Publish event to event bus."""
        ...

    def subscribe(self, event_type: str, handler_function: Any) -> None:
        """Subscribe to event type."""
        ...


class RepositoryBase(ABC):
    """Base repository interface for data access."""

    @abstractmethod
    async def find_by_id(self, entity_id: UUID) -> Any | None:
        """Find entity by ID."""

    @abstractmethod
    async def find_by_user(self, user_id: UUID) -> list[Any]:
        """Find all entities for user."""

    @abstractmethod
    async def save(self, entity: Any) -> Any:
        """Save entity."""

    @abstractmethod
    async def delete(self, entity_id: UUID) -> bool:
        """Delete entity."""


# Event type constants to prevent string duplication
class EventTypes:
    """Centralized event type definitions."""

    # Content lifecycle events
    CONTENT_CREATED = "content_created"
    CONTENT_UPDATED = "content_updated"
    CONTENT_DELETED = "content_deleted"

    # Progress events
    PROGRESS_UPDATED = "progress_updated"
    MILESTONE_REACHED = "milestone_reached"
    CONTENT_COMPLETED = "content_completed"

    # Book-specific events
    BOOK_CREATED = "book_created"
    BOOK_UPLOADED = "book_uploaded"
    BOOK_PAGE_CHANGED = "book_page_changed"
    CHAPTER_COMPLETED = "chapter_completed"

    # Video-specific events
    VIDEO_CREATED = "video_created"
    VIDEO_POSITION_CHANGED = "video_position_changed"
    VIDEO_COMPLETED = "video_completed"

    # Course-specific events
    COURSE_CREATED = "course_created"
    LESSON_COMPLETED = "lesson_completed"
    COURSE_COMPLETED = "course_completed"

    # AI/Processing events
    CONTENT_PROCESSING_STARTED = "content_processing_started"
    CONTENT_PROCESSING_COMPLETED = "content_processing_completed"
    CONTENT_INDEXED = "content_indexed"

    # User events
    USER_LOGIN = "user_login"
    USER_PREFERENCES_UPDATED = "user_preferences_updated"


# Common data structures
class ProgressData:
    """Standardized progress data structure."""

    def __init__(
        self,
        content_id: UUID,
        user_id: UUID,
        completion_percentage: float,
        last_accessed: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.content_id = content_id
        self.user_id = user_id
        self.completion_percentage = completion_percentage
        self.last_accessed = last_accessed
        self.metadata = metadata or {}


class ContentMetadata:
    """Standardized content metadata structure."""

    def __init__(
        self,
        content_id: UUID,
        title: str,
        content_type: str,
        created_by: UUID,
        created_at: str,
        tags: list[str] | None = None,
        summary: str | None = None,
        additional_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.content_id = content_id
        self.title = title
        self.content_type = content_type
        self.created_by = created_by
        self.created_at = created_at
        self.tags = tags or []
        self.summary = summary
        self.additional_metadata = additional_metadata or {}
