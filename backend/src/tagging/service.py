"""Core tagging service for content classification."""

import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.ai.client import ModelManager, TagGenerationError
from src.ai.constants import TAG_CATEGORIES, TAG_CATEGORY_COLORS

from .models import Tag, TagAssociation
from .schemas import TagWithConfidence


logger = logging.getLogger(__name__)


class TaggingService:
    """Service for managing content tags."""

    def __init__(self, session: AsyncSession, model_manager: ModelManager) -> None:
        """Initialize tagging service.

        Args:
            session: Database session
            model_manager: AI model manager for tag generation
        """
        self.session = session
        self.model_manager = model_manager

    async def tag_content(
        self,
        content_id: UUID,
        content_type: str,
        title: str = "",
        content_preview: str = "",
    ) -> list[str]:
        """Generate and store tags for content.

        Args:
            content_id: ID of the content to tag
            content_type: Type of content (book, video, roadmap)
            title: Title of the content
            content_preview: Preview text for tag generation

        Returns
        -------
            List of generated tag names
        """
        try:
            # Generate tags using AI
            tags = await self.model_manager.generate_content_tags(
                content_type=content_type,
                title=title,
                content_preview=content_preview,
            )

            # Store tags in database
            tag_objects = await self._get_or_create_tags(tags)

            # Create associations
            for tag_obj in tag_objects:
                await self._create_tag_association(
                    tag_id=tag_obj.id,
                    content_id=content_id,
                    content_type=content_type,
                    confidence_score=1.0,
                    auto_generated=True,
                )

            await self.session.commit()

            return tags

        except TagGenerationError:
            logger.exception(f"Failed to generate tags for {content_type} {content_id}")
            return []
        except Exception as e:
            logger.exception(f"Error tagging content {content_id}: {e}")
            await self.session.rollback()
            raise

    async def tag_content_with_confidence(
        self,
        content_id: UUID,
        content_type: str,
        title: str = "",
        content_preview: str = "",
    ) -> list[TagWithConfidence]:
        """Generate and store tags with confidence scores.

        Args:
            content_id: ID of the content to tag
            content_type: Type of content (book, video, roadmap)
            title: Title of the content
            content_preview: Preview text for tag generation

        Returns
        -------
            List of tags with confidence scores
        """
        try:
            # Generate tags with confidence using AI
            tags_with_confidence = await self.model_manager.generate_tags_with_confidence(
                content_type=content_type,
                title=title,
                content_preview=content_preview,
            )

            # Extract tag names
            tag_names = [item["tag"] for item in tags_with_confidence]

            # Store tags in database
            tag_objects = await self._get_or_create_tags(tag_names)
            tag_map = {tag.name: tag for tag in tag_objects}

            # Create associations with confidence scores
            result = []
            for item in tags_with_confidence:
                tag_name = item["tag"]
                confidence = item["confidence"]

                if tag_name in tag_map:
                    await self._create_tag_association(
                        tag_id=tag_map[tag_name].id,
                        content_id=content_id,
                        content_type=content_type,
                        confidence_score=confidence,
                        auto_generated=True,
                    )
                    result.append(TagWithConfidence(tag=tag_name, confidence=confidence))

            await self.session.commit()

            return result

        except TagGenerationError:
            logger.exception(f"Failed to generate tags for {content_type} {content_id}")
            return []
        except Exception as e:
            logger.exception(f"Error tagging content {content_id}: {e}")
            await self.session.rollback()
            raise

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

                tags = await self.tag_content(
                    content_id=content_id,
                    content_type=content_type,
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
    ) -> list[Tag]:
        """Get all tags for a content item.

        Args:
            content_id: ID of the content
            content_type: Type of content

        Returns
        -------
            List of Tag objects
        """
        query = (
            select(Tag)
            .join(TagAssociation)
            .where(
                and_(
                    TagAssociation.content_id == content_id,
                    TagAssociation.content_type == content_type,
                ),
            )
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_manual_tags(
        self,
        content_id: UUID,
        content_type: str,
        tag_names: list[str],
    ) -> None:
        """Update manual tags for content, replacing auto-generated ones.

        Args:
            content_id: ID of the content
            content_type: Type of content
            tag_names: List of tag names to set
        """
        # Delete existing associations
        from sqlalchemy import delete

        await self.session.execute(
            delete(TagAssociation).where(
                and_(
                    TagAssociation.content_id == content_id,
                    TagAssociation.content_type == content_type,
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
                confidence_score=1.0,
                auto_generated=False,
            )

        await self.session.commit()

    async def suggest_tags(
        self,
        content_preview: str,
        content_type: str = "general",
        title: str = "",
    ) -> list[str]:
        """Suggest tags for content without storing them.

        Args:
            content_preview: Preview text for tag generation
            content_type: Type of content
            title: Optional title

        Returns
        -------
            List of suggested tag names
        """
        try:
            return await self.model_manager.generate_content_tags(
                content_type=content_type,
                title=title,
                content_preview=content_preview,
            )
        except TagGenerationError:
            logger.exception("Failed to generate tag suggestions")
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
                # Determine category and color
                category = self._determine_tag_category(name)
                color = TAG_CATEGORY_COLORS.get(category, TAG_CATEGORY_COLORS["default"])

                tag = Tag(
                    name=name,
                    category=category,
                    color=color,
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
        confidence_score: float = 1.0,
        auto_generated: bool = True,
    ) -> TagAssociation:
        """Create a tag association.

        Args:
            tag_id: ID of the tag
            content_id: ID of the content
            content_type: Type of content
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
                ),
            ),
        )

        if existing.scalar_one_or_none():
            return existing.scalar_one()

        # Create new association
        association = TagAssociation(
            tag_id=tag_id,
            content_id=content_id,
            content_type=content_type,
            confidence_score=confidence_score,
            auto_generated=auto_generated,
        )

        self.session.add(association)
        return association

    def _determine_tag_category(self, tag_name: str) -> str:
        """Determine the category of a tag based on its name.

        Args:
            tag_name: Name of the tag

        Returns
        -------
            Category name
        """
        for category, tags in TAG_CATEGORIES.items():
            if tag_name in tags:
                return category
        return "default"


async def update_content_tags_json(
    session: AsyncSession,
    content_id: UUID,
    content_type: str,
    tags: list[str],
) -> None:
    """Update the tags_json field for a content item.

    This is a utility function to maintain backward compatibility
    with the existing tags_json fields in Book, Video, and Roadmap models.

    Args:
        session: Database session
        content_id: ID of the content
        content_type: Type of content (book, video, roadmap)
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
            update(Video).where(Video.uuid == content_id).values(tags=tags_json),
        )
    elif content_type == "roadmap":
        from sqlalchemy import update

        from src.roadmaps.models import Roadmap

        await session.execute(
            update(Roadmap).where(Roadmap.id == content_id).values(tags_json=tags_json),
        )

    await session.flush()
