"""Script to extract table of contents for all existing books."""

import asyncio
import logging

from sqlalchemy import select

from src.books.models import Book
from src.books.service import extract_and_update_toc
from src.database.session import async_session_maker


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def extract_toc_for_all_books() -> None:
    """Extract table of contents for all books that don't have it."""
    async with async_session_maker() as session:
        # Get all books without table of contents
        query = select(Book).where(
            (Book.table_of_contents.is_(None)) | (Book.table_of_contents == ""),
        )
        result = await session.execute(query)
        books = result.scalars().all()

        logger.info(f"Found {len(books)} books without table of contents")

        for book in books:
            try:
                logger.info(f"Extracting TOC for: {book.title} (ID: {book.id})")
                await extract_and_update_toc(book.id)
                logger.info(f"✓ Successfully extracted TOC for: {book.title}")
            except Exception as e:
                logger.exception(f"✗ Failed to extract TOC for {book.title}: {e}")

        logger.info("Finished processing all books")


if __name__ == "__main__":
    asyncio.run(extract_toc_for_all_books())
