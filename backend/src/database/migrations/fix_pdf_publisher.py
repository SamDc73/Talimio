#!/usr/bin/env python3
"""Migration to fix incorrect publisher data (was using PDF producer instead of actual publisher)."""

import asyncio
import logging

from sqlalchemy import select

from src.books.models import Book
from src.database.session import async_session_maker


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Known PDF producers that are NOT publishers
PDF_PRODUCERS = [
    "Antenna House PDF Output Library",
    "pdfTeX",
    "LaTeX",
    "Adobe Acrobat",
    "Microsoft Word",
    "LibreOffice",
    "Google Docs",
    "Ghostscript",
    "wkhtmltopdf",
    "Prince",
    "XeTeX",
    "pdftk",
    "iText",
    "Apache FOP",
    "Cairo",
]


async def run_migration():
    """Clear publisher field for PDFs where it's actually PDF producer software."""
    async with async_session_maker() as db:
        try:
            # Get all PDF books with publisher field set
            query = select(Book).where(Book.file_type == "pdf", Book.publisher.is_not(None), Book.publisher != "")

            result = await db.execute(query)
            books = result.scalars().all()
            logger.info(f"Found {len(books)} PDF books with publisher data")

            cleared_count = 0
            for book in books:
                # Check if publisher is actually a PDF producer
                is_producer = False
                for producer in PDF_PRODUCERS:
                    if producer.lower() in book.publisher.lower():
                        is_producer = True
                        break

                if is_producer:
                    logger.info(f"Clearing incorrect publisher '{book.publisher}' for: {book.title}")
                    book.publisher = None
                    cleared_count += 1
                else:
                    logger.info(f"Keeping publisher '{book.publisher}' for: {book.title} (looks legitimate)")

            # Commit all updates
            await db.commit()
            logger.info(f"Migration complete. Cleared {cleared_count}/{len(books)} incorrect publisher entries")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
