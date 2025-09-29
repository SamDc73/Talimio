"""Content archive service."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService


logger = logging.getLogger(__name__)


class ContentArchiveService:
    """Service for archiving and unarchiving content."""

    @staticmethod
    async def archive_content(db: AsyncSession, content_type: ContentType, content_id: UUID, user_id: UUID) -> None:
        """Archive content by type and ID with user validation."""
        table_map = {
            ContentType.BOOK: "books",
            ContentType.YOUTUBE: "videos",
            ContentType.COURSE: "roadmaps",
        }

        table_name = table_map.get(content_type)
        if not table_name:
            msg = f"Unsupported content type: {content_type}"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"🗃️ Archiving {content_type} {content_id} in table {table_name}")

        # Handle different ID column names
        id_column = "uuid" if content_type == ContentType.YOUTUBE else "id"

        # Update with user validation
        query = f"""
            UPDATE {table_name}
            SET archived = true, archived_at = :archived_at
            WHERE {id_column} = :content_id AND user_id = :user_id
        """

        logger.info(f"🔍 Executing query: {query}")
        logger.info(f"🔍 With params: content_id={content_id}, user_id={user_id}")

        result = await db.execute(
            text(query), {"content_id": content_id, "user_id": user_id, "archived_at": datetime.now(UTC)}
        )
        affected_rows = result.rowcount
        await db.commit()

        logger.info(f"📊 Archive operation affected {affected_rows} rows")

        if affected_rows == 0:
            msg = f"Content {content_id} not found or access denied"
            logger.warning(f"⚠️ {msg}")
            raise ValueError(msg)
        logger.info(f"✅ Successfully archived {content_id}")

    @staticmethod
    async def unarchive_content(db: AsyncSession, content_type: ContentType, content_id: UUID, user_id: UUID) -> None:
        """Unarchive content by type and ID with user validation."""
        table_map = {
            ContentType.BOOK: "books",
            ContentType.YOUTUBE: "videos",
            ContentType.COURSE: "roadmaps",
        }

        table_name = table_map.get(content_type)
        if not table_name:
            msg = f"Unsupported content type: {content_type}"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"📤 Unarchiving {content_type} {content_id} in table {table_name}")

        # Handle different ID column names
        id_column = "uuid" if content_type == ContentType.YOUTUBE else "id"

        # Update with user validation
        query = f"""
            UPDATE {table_name}
            SET archived = false, archived_at = NULL
            WHERE {id_column} = :content_id AND user_id = :user_id
        """

        logger.info(f"🔍 Executing unarchive query: {query}")
        logger.info(f"🔍 With params: content_id={content_id}, user_id={user_id}")

        result = await db.execute(text(query), {"content_id": content_id, "user_id": user_id})
        affected_rows = result.rowcount
        await db.commit()

        logger.info(f"📊 Unarchive operation affected {affected_rows} rows")

        if affected_rows == 0:
            msg = f"Content {content_id} not found or access denied"
            logger.warning(f"⚠️ {msg}")
            raise ValueError(msg)
        logger.info(f"✅ Successfully unarchived {content_id}")

    @staticmethod
    async def list_archived_content(
        search: str | None = None,
        content_type: ContentType | None = None,
        page: int = 1,
        page_size: int = 20,
        current_user_id: UUID | None = None,
    ) -> ContentListResponse:
        """
        List only archived content across different types.

        Similar to list_content_fast but filters for archived = true.
        """
        from src.content.services.content_service import ContentService
        from src.database.session import async_session_maker

        offset = (page - 1) * page_size
        search_term = f"%{search}%" if search else None

        # Construct the combined query with archived filter
        if content_type:
            if content_type == ContentType.YOUTUBE:
                combined_query = QueryBuilderService.get_youtube_query(search, archived_only=True)
            elif content_type == ContentType.BOOK:
                combined_query = QueryBuilderService.get_books_query(
                    search, archived_only=True, user_id=current_user_id
                )
            elif content_type == ContentType.COURSE:
                combined_query = QueryBuilderService.get_roadmaps_query(
                    search, archived_only=True, user_id=current_user_id
                )
            else:
                msg = f"Unsupported content type: {content_type}"
                raise ValueError(msg)
        else:
            # Union all content types with archived filter
            combined_query = f"""
                {QueryBuilderService.get_youtube_query(search, archived_only=True)}
                UNION ALL
                {QueryBuilderService.get_books_query(search, archived_only=True, user_id=current_user_id)}
                UNION ALL
                {QueryBuilderService.get_roadmaps_query(search, archived_only=True, user_id=current_user_id)}
            """

        async with async_session_maker() as session:
            # Get total count and paginated results
            total = await QueryBuilderService.get_total_count(session, combined_query, search_term, current_user_id)
            service = ContentService()
            rows = await service.get_paginated_results(
                session, combined_query, search_term, page_size, offset, current_user_id
            )

            # Transform rows to content items
            items = ContentTransformService.transform_rows_to_items(rows)

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            per_page=page_size,
        )
