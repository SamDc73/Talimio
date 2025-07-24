"""Mode-aware service utilities for handling single-user vs multi-user modes."""

from typing import TypeVar
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.orm import DeclarativeBase

from src.config.settings import get_settings


# Type variable for SQLAlchemy models
ModelType = TypeVar("ModelType", bound=DeclarativeBase)


class ModeAwareQueryBuilder[ModelType: DeclarativeBase]:
    """Helper class for building mode-aware database queries."""

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model
        self.settings = get_settings()
        self.is_multi_user = self.settings.AUTH_PROVIDER == "supabase"

    def apply_user_filter(self, query: Select[tuple[ModelType]], user_id: UUID) -> Select[tuple[ModelType]]:
        """Apply user filtering based on authentication mode.

        Args:
            query: Base SQLAlchemy query
            user_id: User ID for filtering records

        Returns
        -------
            Modified query with appropriate user filtering
        """
        # Check if the model has a user_id column
        if not hasattr(self.model, "user_id"):
            # If no user_id column, return query unchanged
            return query

        if self.is_multi_user:
            # In multi-user mode, filter by authenticated user OR DEFAULT_USER_ID (for legacy data)
            from src.config.settings import DEFAULT_USER_ID
            return query.where(
                (self.model.user_id == user_id) |
                (self.model.user_id == DEFAULT_USER_ID)
            )
        # In single-user mode, we could either:
        # 1. Not filter at all (everything belongs to everyone)
        # 2. Filter by DEFAULT_USER_ID
        # For now, we'll filter by the user_id to maintain consistency
        return query.where(self.model.user_id == user_id)

    def apply_user_filter_for_creation(self, user_id: UUID) -> UUID:
        """Get the user ID to use when creating new records.

        Args:
            user_id: User ID to use for creation

        Returns
        -------
            UUID to use for the user_id field
        """
        return user_id

    def validate_user_ownership(self, record: ModelType, user_id: UUID) -> bool:
        """Validate that a user owns a specific record.

        Args:
            record: Database record to check
            user_id: User ID to check ownership against

        Returns
        -------
            True if user owns the record or if in single-user mode
        """
        # Check if the model has a user_id column
        if not hasattr(record, "user_id"):
            # If no user_id column, assume accessible
            return True

        if self.is_multi_user:
            # In multi-user mode, allow access to user's own records OR legacy DEFAULT_USER_ID records
            from src.config.settings import DEFAULT_USER_ID
            return record.user_id in (user_id, DEFAULT_USER_ID)
        # In single-user mode, everything is accessible
        return True


class ModeAwareService:
    """Base class for services that need to handle both authentication modes."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.is_multi_user = self.settings.AUTH_PROVIDER == "supabase"

    def get_query_builder(self, model: type[ModelType]) -> ModeAwareQueryBuilder[ModelType]:
        """Get a query builder for the specified model.

        Args:
            model: SQLAlchemy model class

        Returns
        -------
            Configured query builder
        """
        return ModeAwareQueryBuilder(model)

    def log_access(self, action: str, user_id: UUID, resource_type: str, resource_id: str | None = None) -> None:
        """Log resource access for debugging and auditing.

        Args:
            action: Action being performed (e.g., "get", "create", "update", "delete")
            user_id: User ID for access logging
            resource_type: Type of resource being accessed (e.g., "book", "video", "course")
            resource_id: Optional resource identifier
        """
        import logging
        logger = logging.getLogger(__name__)

        logger.info(
            f"Resource access: {action} {resource_type}",
            extra={
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "user_id": str(user_id),
                "is_multi_user": self.is_multi_user,
            }
        )
