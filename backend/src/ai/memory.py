"""
Simplified async memory manager using mem0's AsyncMemory.

Key optimizations:
- Single initialization - reuses AsyncMemory client across all calls
- Let mem0 handle all connection pooling internally
- Minimal wrapper - rely on mem0's built-in features
- Proper error handling without breaking the flow
"""

import logging
from typing import Any
from uuid import UUID

from mem0.configs.base import MemoryConfig

from mem0 import AsyncMemory
from src.config import env
from src.config.settings import get_settings


logger = logging.getLogger(__name__)

# Module-level instance - initialized once at startup
_memory_client: AsyncMemory | None = None


def _get_memory_config() -> dict[str, Any]:
    """Build mem0 configuration from environment."""
    settings = get_settings()

    # Convert database URL for psycopg3
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql+psycopg://"):
        connection_string = database_url.replace("postgresql+psycopg://", "postgresql://")
    elif database_url.startswith("postgresql://"):
        connection_string = database_url
    else:
        msg = f"Unsupported DATABASE_URL format: {database_url}"
        raise ValueError(msg)

    # Extract model names (mem0 doesn't need provider prefix)
    embed_model = env("MEMORY_EMBEDDING_MODEL").split("/")[-1]
    embedding_dims = int(env("MEMORY_EMBEDDING_OUTPUT_DIM"))

    return {
        "vector_store": {
            "provider": "pgvector",
            "config": {
                "connection_string": connection_string,
                "collection_name": "learning_memories",
                "embedding_model_dims": embedding_dims,
                "hnsw": True,  # Use HNSW for faster search
                "minconn": 1,  # Min pool connections
                "maxconn": 3,  # Reduced to prevent competition with SQLAlchemy pool
            },
        },
        "llm": {
            "provider": "litellm",
            "config": {
                "model": env("MEMORY_LLM_MODEL"),
                "temperature": 0.2,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embed_model,
                "embedding_dims": embedding_dims,
            },
        },
    }


async def get_memory_client() -> AsyncMemory:
    """Get or create the singleton AsyncMemory client."""
    global _memory_client  # noqa: PLW0603

    if _memory_client is None:
        try:
            config = _get_memory_config()
            mem0_config = MemoryConfig(**config)
            _memory_client = AsyncMemory(mem0_config)
            logger.info("AsyncMemory client initialized with connection pooling")
        except Exception as e:
            logger.exception(f"Failed to initialize AsyncMemory: {e}")
            raise

    return _memory_client


async def add_memory(user_id: UUID, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add memory for a user."""
    try:
        client = await get_memory_client()

        # Prepare metadata
        if metadata is None:
            metadata = {}
        metadata["user_id"] = str(user_id)

        # Add memory using mem0's async method
        result = await client.add(
            messages=[{"role": "user", "content": content}],
            user_id=str(user_id),
            metadata=metadata
        )

        logger.debug(f"Added memory for user {user_id}")
        return result or {}

    except Exception as e:
        logger.warning(f"Failed to add memory for user {user_id}: {e}")
        return {}  # Don't break the flow


async def get_memories(user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
    """Get all memories for a user."""
    try:
        client = await get_memory_client()
        results = await client.get_all(
            user_id=str(user_id),
            limit=limit
        )

        if isinstance(results, dict):
            return results.get("results", [])
        return []

    except Exception as e:
        logger.warning(f"Failed to get memories for user {user_id}: {e}")
        return []


async def search_memories(
    user_id: UUID, query: str, limit: int = 5, threshold: float | None = None
) -> list[dict[str, Any]]:
    """Search memories for a user."""
    # Handle empty queries
    if not query or not query.strip():
        logger.debug(f"Empty query, using get_memories for user {user_id}")
        return await get_memories(user_id, limit)

    try:
        client = await get_memory_client()
        results = await client.search(
            query=query,
            user_id=str(user_id),
            limit=limit,
            threshold=threshold
        )

        if isinstance(results, dict):
            return results.get("results", [])
        return []

    except Exception as e:
        logger.warning(f"Memory search failed for user {user_id}: {e}")
        return []


async def delete_memory(user_id: UUID, memory_id: str) -> bool:
    """Delete a specific memory."""
    try:
        client = await get_memory_client()
        await client.delete(memory_id)
        logger.info(f"Deleted memory {memory_id} for user {user_id}")
        return True

    except Exception as e:
        logger.warning(f"Failed to delete memory {memory_id}: {e}")
        return False


async def cleanup_memory_client() -> None:
    """Cleanup the memory client on shutdown."""
    global _memory_client  # noqa: PLW0603

    if _memory_client is not None:
        try:
            # mem0 manages its own connection pools internally
            # Just clear the reference
            _memory_client = None
            logger.info("Memory client reference cleared")
        except Exception as e:
            logger.warning(f"Error during memory cleanup: {e}")
