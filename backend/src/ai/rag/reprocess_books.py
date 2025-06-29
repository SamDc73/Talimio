"""Reprocess all books with updated chunking that includes metadata."""

import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import text

from src.ai.rag.chunk_storage import ChunkStorageService
from src.ai.rag.chunker import ChunkerFactory
from src.database.session import async_session_maker


# Load environment variables after imports
env_path = Path(__file__).parent.parent.parent.parent / ".env"
load_dotenv(env_path)


logger = logging.getLogger(__name__)


async def reprocess_book(book_id: UUID) -> dict:
    """Reprocess a single book with metadata-aware chunking."""
    chunk_storage = ChunkStorageService()

    async with async_session_maker() as session:
        # Get book metadata and file path
        result = await session.execute(
            text("SELECT title, author, subtitle, description, file_path FROM books WHERE id = :book_id"),
            {"book_id": str(book_id)},
        )
        book_data = result.fetchone()

        if not book_data:
            return {"status": "error", "message": f"Book {book_id} not found"}

        # Create book metadata
        book_metadata = {
            "title": book_data.title,
            "author": book_data.author,
            "subtitle": book_data.subtitle,
            "description": book_data.description,
        }

        logger.info(f"Reprocessing book: {book_data.title} by {book_data.author}")

        # Create chunker with metadata
        chunker = ChunkerFactory.create_chunker("book", _metadata=book_metadata)

        # Chunk the document (convert relative path to absolute)
        file_path = book_data.file_path
        if not Path(file_path).is_absolute():
            # Assume relative to backend directory
            file_path = str(Path(__file__).parent.parent.parent.parent / file_path)

        chunks = chunker.chunk_document(book_id, "book", file_path)

        if not chunks:
            return {"status": "error", "message": "No chunks generated"}

        # Delete existing chunks
        deleted_count = await chunk_storage.delete_document_chunks(book_id)

        # Store new chunks
        await chunk_storage.store_document_chunks(book_id, "book", chunks)

        # Get final count
        final_count = await chunk_storage.get_document_chunk_count(book_id)

        return {
            "status": "success",
            "book_title": book_data.title,
            "book_author": book_data.author,
            "chunks_deleted": deleted_count,
            "chunks_created": final_count,
        }


async def reprocess_all_books() -> list[dict]:
    """Reprocess all books in the database."""
    results = []

    async with async_session_maker() as session:
        # Get all book IDs
        result = await session.execute(text("SELECT id, title FROM books"))
        books = result.fetchall()

        logger.info(f"Found {len(books)} books to reprocess")

        for book in books:
            try:
                book_result = await reprocess_book(book.id)
                results.append(book_result)
            except Exception as e:
                logger.exception(f"Failed to reprocess book {book.id}: {e}")
                results.append({"status": "error", "book_title": book.title, "message": str(e)})

    return results


# For running as a script
if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Process specific book
        book_id = UUID(sys.argv[1])
        result = asyncio.run(reprocess_book(book_id))
        logger.info(f"Result: {result}")
    else:
        # Process all books
        results = asyncio.run(reprocess_all_books())
        for result in results:
            logger.info(f"Result: {result}")
