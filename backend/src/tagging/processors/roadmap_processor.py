"""Roadmap content processor for tag generation."""

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.roadmaps.models import Roadmap


logger = logging.getLogger(__name__)


class RoadmapProcessor:
    """Processor for extracting roadmap content for tagging."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize roadmap processor.

        Args:
            session: Database session
        """
        self.session = session

    async def extract_content_for_tagging(
        self,
        roadmap: Roadmap,
    ) -> dict[str, str]:
        """Extract roadmap content for tag generation.

        Args:
            roadmap: Roadmap model instance

        Returns
        -------
            Dictionary with title, description, and content_preview
        """
        # Build content preview from roadmap metadata and node structure
        content_parts = []

        # Add roadmap description
        if roadmap.description:
            content_parts.append(f"Description: {roadmap.description}")

        # Add skill level context
        content_parts.append(f"Skill Level: {roadmap.skill_level}")

        # Add node titles and descriptions for better context
        if roadmap.nodes:
            node_summaries = []
            for node in roadmap.nodes[:10]:  # Limit to first 10 nodes
                node_summary = f"- {node.title}"
                if node.description:
                    # Take first 200 chars of description
                    desc_preview = node.description[:200]
                    if len(node.description) > 200:
                        desc_preview += "..."
                    node_summary += f": {desc_preview}"
                node_summaries.append(node_summary)

            if node_summaries:
                content_parts.append("Learning Topics:")
                content_parts.extend(node_summaries)

        # Add existing tags if any
        if roadmap.tags_json:
            try:
                existing_tags = json.loads(roadmap.tags_json)
                if existing_tags:
                    content_parts.append(f"Existing tags: {', '.join(existing_tags[:10])}")
            except Exception as e:
                logger.debug(f"Failed to parse existing roadmap tags: {e}")

        return {
            "title": roadmap.title,
            "description": roadmap.description or "",
            "content_preview": "\n\n".join(content_parts),
        }


async def process_roadmap_for_tagging(
    roadmap_id: UUID,
    session: AsyncSession,
) -> dict[str, str] | None:
    """Process a roadmap to extract content for tagging.

    Args:
        roadmap_id: UUID of the roadmap to process
        session: Database session

    Returns
    -------
        Dictionary with title, description, and content_preview, or None if not found
    """
    # Get roadmap from database with nodes
    from sqlalchemy.orm import selectinload

    result = await session.execute(
        select(Roadmap).options(selectinload(Roadmap.nodes)).where(Roadmap.id == roadmap_id),
    )
    roadmap = result.scalar_one_or_none()

    if not roadmap:
        logger.error(f"Roadmap not found: {roadmap_id}")
        return None

    # Process roadmap
    processor = RoadmapProcessor(session)
    return await processor.extract_content_for_tagging(roadmap)
