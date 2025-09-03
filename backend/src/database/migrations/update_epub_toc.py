#!/usr/bin/env python3
"""Migration to extract and update table of contents for existing EPUB books."""

import asyncio
import json
import logging

import fitz  # PyMuPDF
from sqlalchemy import select

from src.books.models import Book
from src.database.session import async_session_maker
from src.storage.factory import get_storage_provider


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def process_toc(toc: list) -> list[dict]:
    """Process PyMuPDF table of contents into a structured format."""
    result: list[dict] = []
    stack: list[dict] = []  # Stack to track parent chapters

    for i, entry in enumerate(toc):
        level, title, page = entry

        # Create TOC item
        item = {
            "id": f"toc_{i}_{level}_{page}",
            "title": title.strip(),
            "page": page,
            "level": level - 1,  # Make it 0-based
            "children": [],
        }

        # Handle hierarchy
        while stack and stack[-1]["level"] >= item["level"]:
            stack.pop()

        if stack:
            # Add as child to parent
            stack[-1]["children"].append(item)
        else:
            # Top-level item
            result.append(item)

        # Add to stack for potential children
        stack.append(item)

    return result


async def extract_epub_toc(file_content: bytes) -> list[dict] | None:
    """Extract table of contents from EPUB content."""
    try:
        # Open EPUB with PyMuPDF
        epub_document = fitz.open(stream=file_content, filetype="epub")

        # Get table of contents
        toc = epub_document.get_toc()

        result = None
        if toc:
            result = await process_toc(toc)
            logger.info(f"Extracted {len(toc)} TOC entries")
        else:
            logger.info("No TOC found in EPUB")

        epub_document.close()
        return result

    except Exception as e:
        logger.error(f"Failed to extract TOC: {e}")
        return None


async def run_migration():
    """Update table_of_contents for existing EPUB books."""
    async with async_session_maker() as db:
        try:
            # Get all EPUB books without table_of_contents
            query = select(Book).where(
                Book.file_type == "epub", (Book.table_of_contents.is_(None)) | (Book.table_of_contents == "[]")
            )

            result = await db.execute(query)
            books = result.scalars().all()
            logger.info(f"Found {len(books)} EPUB books without TOC")

            if not books:
                logger.info("No EPUB books need TOC extraction")
                return

            # Get storage provider
            storage = get_storage_provider()

            updated_count = 0
            for book in books:
                logger.info(f"Processing: {book.title}")

                try:
                    # Download file from storage
                    file_content = await storage.download(book.file_path)

                    # Extract TOC
                    toc = await extract_epub_toc(file_content)

                    if toc:
                        # Update database
                        book.table_of_contents = json.dumps(toc)
                        updated_count += 1
                        logger.info(f"Updated TOC for: {book.title}")
                    else:
                        logger.warning(f"No TOC extracted for: {book.title}")

                except Exception as e:
                    logger.error(f"Failed to process {book.title}: {e}")
                    continue

            # Commit all updates
            await db.commit()
            logger.info(f"Migration complete. Updated {updated_count}/{len(books)} books")

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    asyncio.run(run_migration())
