"""Content delete service."""

import logging
from uuid import UUID

from sqlalchemy import select, text

from src.content.schemas import ContentType
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class ContentDeleteService:
    """Service for deleting content."""

    @staticmethod
    async def delete_content(content_type: ContentType, content_id: str) -> None:
        """Delete content by type and ID using proper ORM cascade deletion."""
        # Import the models for proper ORM deletion
        if content_type == ContentType.BOOK:
            from src.books.models import Book as ModelClass
        elif content_type == ContentType.YOUTUBE:
            from src.videos.models import Video as ModelClass
        elif content_type == ContentType.FLASHCARDS:
            from src.flashcards.models import FlashcardDeck as ModelClass
        elif content_type == ContentType.COURSE:
            from src.courses.models import Roadmap as ModelClass
        else:
            msg = f"Unsupported content type: {content_type}"
            raise ValueError(msg)

        async with async_session_maker() as session:
            # Handle different ID column names and types
            if content_type == ContentType.YOUTUBE:
                # Videos use uuid column, need to query by uuid field
                stmt = select(ModelClass).where(ModelClass.uuid == content_id)
                result = await session.execute(stmt)
                content_obj = result.scalar_one_or_none()
            else:
                # Convert string ID to UUID for other content types
                try:
                    uuid_id = UUID(content_id)
                    content_obj = await session.get(ModelClass, uuid_id)
                except ValueError as ve:
                    msg = f"Invalid ID format: {content_id}"
                    raise ValueError(msg) from ve

            if not content_obj:
                msg = f"Content with ID {content_id} not found"
                raise ValueError(msg)

            # Special handling for roadmaps to fix foreign key constraint issues
            if content_type == ContentType.COURSE:
                # First, delete all nodes that reference this roadmap in correct order
                # Delete child nodes first, then parent nodes to avoid foreign key violations
                await session.execute(
                    text("""
                        WITH RECURSIVE node_hierarchy AS (
                            -- Find leaf nodes (no children)
                            SELECT id, parent_id, 0 as level
                            FROM nodes
                            WHERE roadmap_id = :roadmap_id
                            AND id NOT IN (SELECT parent_id FROM nodes WHERE parent_id IS NOT NULL AND roadmap_id = :roadmap_id)

                            UNION ALL

                            -- Find parent nodes
                            SELECT n.id, n.parent_id, nh.level + 1
                            FROM nodes n
                            JOIN node_hierarchy nh ON n.id = nh.parent_id
                            WHERE n.roadmap_id = :roadmap_id
                        )
                        DELETE FROM nodes WHERE id IN (SELECT id FROM node_hierarchy)
                    """),
                    {"roadmap_id": uuid_id},
                )

                # Now delete the roadmap itself
                await session.execute(text("DELETE FROM roadmaps WHERE id = :roadmap_id"), {"roadmap_id": uuid_id})
            else:
                # Delete using ORM to ensure proper cascade deletion for other content types
                await session.delete(content_obj)

            await session.commit()
