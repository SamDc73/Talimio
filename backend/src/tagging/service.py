"""Core tagging service for content classification."""

import json
import logging
import os
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import LLMClient
from src.ai.prompts import CONTENT_TAGGING_PROMPT

from .models import Tag, TagAssociation
from .schemas import TagWithConfidence


logger = logging.getLogger(__name__)


class TaggedContent(BaseModel):
    """Structured tagging response enforced by LiteLLM json mode."""

    tags: list[TagWithConfidence] = Field(
        ..., description="List of tags with confidence scores", min_length=1, max_length=10
    )


class TaggingService:
    """Service for managing content tags."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize tagging service.

        Args:
            session: Database session
        """
        self.session = session
        self._llm_client = LLMClient()

    async def _generate_tags_llm(self, title: str, content_preview: str) -> list[dict[str, Any]]:
        """Generate tags using LiteLLM structured outputs (Instructor fallback handled upstream)."""
        model = os.getenv("TAGGING_LLM_MODEL")
        if not model:
            logger.warning("TAGGING_LLM_MODEL not set in environment, skipping tag generation")
            return []

        messages = [
            {"role": "system", "content": CONTENT_TAGGING_PROMPT},
            {"role": "user", "content": f"Title: {title}\n\nContent: {content_preview}"},
        ]

        try:
            result = await self._llm_client.get_completion(
                messages,
                response_model=TaggedContent,
                temperature=0,
                user_id=None,
                model=model,
            )
        except Exception as exc:
            logger.exception("Error generating tags via LiteLLM: %s", exc)
            return []

        if not isinstance(result, TaggedContent):
            logger.warning(
                "Tagging LLM returned unexpected payload type %s", type(result).__name__
            )
            return []

        return [{"tag": tag.tag, "confidence": float(tag.confidence)} for tag in result.tags]

    async def tag_content(
        self,
        content_id: UUID,
        content_type: str,
        user_id: UUID,
        title: str = "",
        content_preview: str = "",
    ) -> list[str]:
        """Generate and store tags for content with confidence scores.

        Args:
            content_id: ID of the content to tag
            content_type: Type of content (book, video, course)
            user_id: User ID for personalized tagging
            title: Title of the content
            content_preview: Preview text for tag generation

        Returns
        -------
            List of generated tag names
        """
        try:
            # Generate tags with confidence using the standard LiteLLM path
            tags_with_confidence = await self._generate_tags_llm(title, content_preview)

            # Extract tag names
            tag_names = [item["tag"] for item in tags_with_confidence]

            # Store tags in database
            tag_objects = await self._get_or_create_tags(tag_names)
            tag_map = {tag.name: tag for tag in tag_objects}

            # Create associations with confidence scores
            for item in tags_with_confidence:
                tag_name = item["tag"]
                confidence = item["confidence"]

                if tag_name in tag_map:
                    await self._create_tag_association(
                        tag_id=tag_map[tag_name].id,
                        content_id=content_id,
                        content_type=content_type,
                        user_id=user_id,
                        confidence_score=confidence,
                        auto_generated=True,
                    )

            # Don't commit here - let the caller handle transaction boundaries
            # This allows the calling service to control when changes are persisted
            await self.session.flush()  # Flush to ensure associations are tracked

            return tag_names

        except Exception as e:
            logger.exception(f"Error tagging content {content_id}: {e}")
            await self.session.rollback()
            return []

    async def batch_tag_content(
        self,
        content_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Tag multiple content items.

        Args:
            content_items: List of dicts with content_id, content_type, title, preview

        Returns
        -------
            Dictionary with results summary
        """
        results = []
        successful = 0
        failed = 0

        for item in content_items:
            try:
                content_id = UUID(item["content_id"])
                content_type = item["content_type"]
                title = item.get("title", "")
                preview = item.get("preview", "")

                # Use user_id from item or raise error if not provided
                if "user_id" not in item:
                    msg = "user_id is required for batch tagging"
                    raise ValueError(msg)
                user_id_for_tag = UUID(item["user_id"])

                tags = await self.tag_content(
                    content_id=content_id,
                    content_type=content_type,
                    user_id=user_id_for_tag,
                    title=title,
                    content_preview=preview,
                )

                results.append(
                    {
                        "content_id": str(content_id),
                        "content_type": content_type,
                        "tags": tags,
                        "success": True,
                    },
                )
                successful += 1

            except Exception as e:
                logger.exception(f"Failed to tag item {item}: {e}")
                results.append(
                    {
                        "content_id": item.get("content_id"),
                        "content_type": item.get("content_type"),
                        "tags": [],
                        "success": False,
                        "error": str(e),
                    },
                )
                failed += 1

        return {
            "results": results,
            "total": len(content_items),
            "successful": successful,
            "failed": failed,
        }

    async def get_content_tags(
        self,
        content_id: UUID,
        content_type: str,
        user_id: UUID | None = None,
    ) -> list[Tag]:
        """Get tags for a content item for a specific user.

        Args:
            content_id: ID of the content
            content_type: Type of content
            user_id: User ID to get tags for

        Returns
        -------
            List of Tag objects
        """
        if not user_id:
            # No user_id means no tags in a user-specific system
            return []

        # Get user-specific tags only
        query_conditions = and_(
            TagAssociation.content_id == content_id,
            TagAssociation.content_type == content_type,
            TagAssociation.user_id == user_id,
        )

        query = select(Tag).join(TagAssociation).where(query_conditions)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_manual_tags(
        self,
        content_id: UUID,
        content_type: str,
        user_id: UUID,
        tag_names: list[str],
    ) -> None:
        """Update manual tags for content, replacing auto-generated ones.

        Args:
            content_id: ID of the content
            content_type: Type of content
            user_id: User ID for the tags
            tag_names: List of tag names to set
        """
        # Delete existing associations
        from sqlalchemy import delete

        await self.session.execute(
            delete(TagAssociation).where(
                and_(
                    TagAssociation.content_id == content_id,
                    TagAssociation.content_type == content_type,
                    TagAssociation.user_id == user_id,
                ),
            ),
        )

        # Create new tags and associations
        tag_objects = await self._get_or_create_tags(tag_names)

        for tag_obj in tag_objects:
            await self._create_tag_association(
                tag_id=tag_obj.id,
                content_id=content_id,
                content_type=content_type,
                user_id=user_id,
                confidence_score=1.0,
                auto_generated=False,
            )

        await self.session.commit()

    async def suggest_tags(
        self,
        content_preview: str,
        _user_id: UUID,
        _content_type: str = "general",
        title: str = "",
    ) -> list[str]:
        """Suggest tags for content without storing them.

        Args:
            content_preview: Preview text for tag generation
            _user_id: User ID for personalized tag suggestions (reserved for future use)
            _content_type: Type of content (reserved for future use)
            title: Optional title

        Returns
        -------
            List of suggested tag names
        """
        try:
            tags_with_confidence = await self._generate_tags_llm(title, content_preview)
            # Return just the tag names for backward compatibility
            return [item["tag"] for item in tags_with_confidence]
        except Exception as e:
            logger.exception(f"Failed to generate tag suggestions: {e}")
            return []

    async def get_all_tags(
        self,
        category: str | None = None,
        limit: int = 100,
    ) -> list[Tag]:
        """Get all tags, optionally filtered by category.

        Args:
            category: Optional category filter
            limit: Maximum number of tags to return

        Returns
        -------
            List of Tag objects
        """
        query = select(Tag).order_by(Tag.usage_count.desc()).limit(limit)

        if category:
            query = query.where(Tag.category == category)

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def _get_or_create_tags(self, tag_names: list[str]) -> list[Tag]:
        """Get existing tags or create new ones.

        Args:
            tag_names: List of tag names

        Returns
        -------
            List of Tag objects
        """
        # Get existing tags
        existing_query = select(Tag).where(Tag.name.in_(tag_names))
        result = await self.session.execute(existing_query)
        existing_tags = {tag.name: tag for tag in result.scalars().all()}

        # Create missing tags
        tags_to_create = []
        for name in tag_names:
            if name not in existing_tags:
                tag = Tag(
                    name=name,
                    category="default",
                    color="#6366F1",  # Default indigo color
                    usage_count=0,
                )
                tags_to_create.append(tag)
                self.session.add(tag)

        if tags_to_create:
            await self.session.flush()

        # Update usage counts
        for tag in existing_tags.values():
            tag.usage_count += 1

        # Return all tags
        return list(existing_tags.values()) + tags_to_create

    async def _create_tag_association(
        self,
        tag_id: UUID,
        content_id: UUID,
        content_type: str,
        user_id: UUID,
        confidence_score: float = 1.0,
        auto_generated: bool = True,
    ) -> TagAssociation:
        """Create a tag association.

        Args:
            tag_id: ID of the tag
            content_id: ID of the content
            content_type: Type of content
            user_id: User ID for the association
            confidence_score: Confidence score (0-1)
            auto_generated: Whether the tag was auto-generated

        Returns
        -------
            Created TagAssociation object
        """
        # Check if association already exists
        existing = await self.session.execute(
            select(TagAssociation).where(
                and_(
                    TagAssociation.tag_id == tag_id,
                    TagAssociation.content_id == content_id,
                    TagAssociation.content_type == content_type,
                    TagAssociation.user_id == user_id,
                ),
            ),
        )

        # Read the scalar exactly once; scalar_one_or_none() consumes the result
        existing_assoc = existing.scalar_one_or_none()
        if existing_assoc is not None:
            return existing_assoc

        # Create new association
        association = TagAssociation(
            tag_id=tag_id,
            content_id=content_id,
            content_type=content_type,
            user_id=user_id,
            confidence_score=confidence_score,
            auto_generated=auto_generated,
        )

        self.session.add(association)
        return association



async def update_content_tags_json(
    session: AsyncSession,
    content_id: UUID,
    content_type: str,
    tags: list[str],
) -> None:
    """Update the tags_json field for a content item.

    This is a utility function to maintain backward compatibility
    with the existing tags_json fields in Book, Video, and Course models.

    Args:
        session: Database session
        content_id: ID of the content
        content_type: Type of content (book, video, course)
        tags: List of tag names
    """
    tags_json = json.dumps(tags)

    if content_type == "book":
        from sqlalchemy import update

        from src.books.models import Book

        await session.execute(
            update(Book).where(Book.id == content_id).values(tags=tags_json),
        )
    elif content_type == "video":
        from sqlalchemy import update

        from src.videos.models import Video

        await session.execute(
            update(Video).where(Video.id == content_id).values(tags=tags_json),
        )
    elif content_type == "course":
        from sqlalchemy import update

        from src.courses.models import Course

        await session.execute(
            update(Course).where(Course.id == content_id).values(tags=tags_json),
        )

    await session.flush()


