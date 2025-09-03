"""
Interface contracts for highlighting services across different content types.

This module defines the common interface that all content-specific highlight services
must implement to ensure consistent behavior and UX across the application.
"""

from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from .schemas import HighlightResponse


class HighlightInterface(ABC):
    """
    Abstract interface for highlighting services.

    All content-specific highlight services (books, videos, etc.) must implement
    this interface to ensure consistent behavior across different content types.
    """

    @abstractmethod
    async def create_highlight(
        self, content_id: UUID, user_id: UUID, highlight_data: dict[str, Any]
    ) -> HighlightResponse:
        """
        Create a new highlight for the specified content.

        Args:
            content_id: The ID of the content being highlighted
            user_id: The ID of the user creating the highlight
            highlight_data: Format-specific highlight data (positions, text, etc.)

        Returns
        -------
            HighlightResponse with the created highlight data

        Raises
        ------
            HTTPException: If content not found or user lacks access
        """

    @abstractmethod
    async def get_highlights(self, content_id: UUID, user_id: UUID) -> list[HighlightResponse]:
        """
        Get all highlights for the specified content.

        Args:
            content_id: The ID of the content
            user_id: The ID of the user requesting highlights

        Returns
        -------
            List of HighlightResponse objects, sorted by creation date

        Raises
        ------
            HTTPException: If content not found or user lacks access
        """

    @abstractmethod
    async def delete_highlight(self, highlight_id: UUID, user_id: UUID) -> bool:
        """
        Delete a specific highlight.

        Args:
            highlight_id: The ID of the highlight to delete
            user_id: The ID of the user requesting deletion

        Returns
        -------
            True if deletion was successful

        Raises
        ------
            HTTPException: If highlight not found or user lacks access
        """

    @abstractmethod
    async def get_highlight(self, highlight_id: UUID, user_id: UUID) -> HighlightResponse:
        """
        Get a specific highlight by ID.

        Args:
            highlight_id: The ID of the highlight
            user_id: The ID of the user requesting the highlight

        Returns
        -------
            HighlightResponse with the highlight data

        Raises
        ------
            HTTPException: If highlight not found or user lacks access
        """

    @abstractmethod
    async def update_highlight(
        self, highlight_id: UUID, user_id: UUID, highlight_data: dict[str, Any]
    ) -> HighlightResponse:
        """
        Update an existing highlight.

        Args:
            highlight_id: The ID of the highlight to update
            user_id: The ID of the user updating the highlight
            highlight_data: New highlight data

        Returns
        -------
            HighlightResponse with the updated highlight data

        Raises
        ------
            HTTPException: If highlight not found or user lacks access
        """
