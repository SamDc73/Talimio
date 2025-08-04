"""Content archive service."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import text

from src.content.schemas import ContentListResponse, ContentType
from src.content.services.content_transform_service import ContentTransformService
from src.content.services.query_builder_service import QueryBuilderService
from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class ContentArchiveService:
    """Service for archiving and unarchiving content."""

    @staticmethod
    async def archive_content(content_type: ContentType, content_id: str) -> None:
        """Archive content by type and ID."""
        table_map = {
            ContentType.BOOK: "books",
            ContentType.YOUTUBE: "videos",
            ContentType.FLASHCARDS: "flashcard_decks",
            ContentType.COURSE: "roadmaps",
        }

        table_name = table_map.get(content_type)
        if not table_name:
            msg = f"Unsupported content type: {content_type}"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"🗃️ Archiving {content_type} {content_id} in table {table_name}")

        async with async_session_maker() as session:
            # Handle different ID column names
            id_column = "uuid" if content_type == ContentType.YOUTUBE else "id"

            query = f"""
                UPDATE {table_name}
                SET archived = true, archived_at = :archived_at
                WHERE {id_column} = :content_id
            """

            logger.info(f"🔍 Executing query: {query}")
            logger.info(f"🔍 With params: content_id={content_id}, archived_at={datetime.now(UTC)}")

            result = await session.execute(text(query), {"content_id": content_id, "archived_at": datetime.now(UTC)})
            affected_rows = result.rowcount
            await session.commit()

            logger.info(f"📊 Archive operation affected {affected_rows} rows")

            if affected_rows == 0:
                logger.warning(f"⚠️ No rows were updated - content {content_id} may not exist")
            else:
                logger.info(f"✅ Successfully archived {content_id}")

    @staticmethod
    async def unarchive_content(content_type: ContentType, content_id: str) -> None:
        """Unarchive content by type and ID."""
        table_map = {
            ContentType.BOOK: "books",
            ContentType.YOUTUBE: "videos",
            ContentType.FLASHCARDS: "flashcard_decks",
            ContentType.COURSE: "roadmaps",
        }

        table_name = table_map.get(content_type)
        if not table_name:
            msg = f"Unsupported content type: {content_type}"
            logger.error(msg)
            raise ValueError(msg)

        logger.info(f"📤 Unarchiving {content_type} {content_id} in table {table_name}")

        async with async_session_maker() as session:
            try:
                # Handle different ID column names
                id_column = "uuid" if content_type == ContentType.YOUTUBE else "id"

                query = f"""
                    UPDATE {table_name}
                    SET archived = false, archived_at = NULL
                    WHERE {id_column} = :content_id
                """

                logger.info(f"🔍 Executing unarchive query: {query}")
                logger.info(f"🔍 With params: content_id={content_id}")

                result = await session.execute(text(query), {"content_id": content_id})
                affected_rows = result.rowcount
                await session.commit()

                logger.info(f"📊 Unarchive operation affected {affected_rows} rows")

                if affected_rows == 0:
                    logger.warning(f"⚠️ No rows were updated - content {content_id} may not exist")
                else:
                    logger.info(f"✅ Successfully unarchived {content_id}")

            except Exception:
                logger.exception(
                    "💥 Database error in unarchive_content. Query: %s, Params: content_id=%s", query, content_id
                )
                await session.rollback()
                raise

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

        offset = (page - 1) * page_size
        search_term = f"%{search}%" if search else None
        # For content listing, we don't require authentication
        # If no user is provided, we'll show content with 0% progress
        # current_user_id is already a string or None from the router
        effective_user_id = current_user_id

        # Construct the combined query with archived filter
        if content_type:
            if content_type == ContentType.YOUTUBE:
                combined_query = QueryBuilderService.get_youtube_query(search, archived_only=True)
            elif content_type == ContentType.FLASHCARDS:
                combined_query = QueryBuilderService.get_flashcards_query(
                    search, archived_only=True, user_id=effective_user_id
                )
            elif content_type == ContentType.BOOK:
                combined_query = QueryBuilderService.get_books_query(
                    search, archived_only=True, user_id=effective_user_id
                )
            elif content_type == ContentType.COURSE:
                combined_query = QueryBuilderService.get_roadmaps_query(
                    search, archived_only=True, user_id=effective_user_id
                )
            else:
                msg = f"Unsupported content type: {content_type}"
                raise ValueError(msg)
        else:
            # Union all content types with archived filter
            combined_query = f"""
                {QueryBuilderService.get_youtube_query(search, archived_only=True)}
                UNION ALL
                {QueryBuilderService.get_flashcards_query(search, archived_only=True, user_id=effective_user_id)}
                UNION ALL
                {QueryBuilderService.get_books_query(search, archived_only=True, user_id=effective_user_id)}
                UNION ALL
                {QueryBuilderService.get_roadmaps_query(search, archived_only=True, user_id=effective_user_id)}
            """

        async with async_session_maker() as session:
            # Get total count and paginated results
            total = await QueryBuilderService.get_total_count(session, combined_query, search_term, effective_user_id)
            rows = await ContentService.get_paginated_results(
                session, combined_query, search_term, page_size, offset, effective_user_id
            )

            # Transform rows to content items
            items = ContentTransformService.transform_rows_to_items(rows)

        return ContentListResponse(
            items=items,
            total=total,
            page=page,
            pageSize=page_size,
        )
