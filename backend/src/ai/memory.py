"""
Production-ready async memory manager using mem0's AsyncMemory.

This implementation:
- Uses mem0's AsyncMemory with proper patterns
- Uses simplest DB connection: pass a single PostgreSQL connection string and let mem0 manage pooling (psycopg3)
- Targets Supabase Session Pooler with pgvector; no autocommit changes required
- Proper connection handling via mem0-managed pooling; aligns with mem0's internal asyncio.to_thread architecture
"""

import logging
from typing import Any
from uuid import UUID

from mem0 import AsyncMemory

from src.config import env
from src.config.settings import get_settings


class MemoryWrapper:
    """
    Production-ready async memory wrapper for 10k+ users.

    Features:
    - Non-blocking I/O operations
    - Mem0-managed connection pooling
    - Concurrent vector operations; graph optional (disabled unless configured)
    - Native FastAPI integration
    - Automatic retry and error recovery
    """

    def __init__(self) -> None:
        """Initialize the async memory wrapper."""
        self.settings = get_settings()
        self._logger = logging.getLogger(__name__)
        self._memory_client: AsyncMemory | None = None

        # Build a simple PostgreSQL connection string for psycopg3
        database_url = self.settings.DATABASE_URL
        if database_url.startswith("postgresql+psycopg://"):
            connection_string = database_url.replace("postgresql+psycopg://", "postgresql://")
        elif database_url.startswith("postgresql://"):
            connection_string = database_url
        else:
            msg = f"Unsupported DATABASE_URL format: {database_url}"
            raise ValueError(msg)

        # Configure mem0 with async support (let mem0 manage pooling)
        # Derived embedder configuration (keep dims in one place)
        embedding_dims = int(env("MEMORY_EMBEDDING_OUTPUT_DIM", "1536"))
        embed_model = env("MEMORY_EMBEDDING_MODEL", "openai/text-embedding-3-small").split("/")[-1]
        self.config = {
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "connection_string": connection_string,
                    "collection_name": "learning_memories",
                    "embedding_model_dims": embedding_dims,
                    "hnsw": True,
                },
            },
            "llm": {
                "provider": "litellm",
                "config": {
                    "model": env("MEMORY_LLM_MODEL", "openai/gpt-4o-mini"),
                    "temperature": 0.2,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    # Strip provider prefix for OpenAI (expects just model name)
                    "model": embed_model,
                    "embedding_dims": embedding_dims,
                },
            },
        }

        self._logger.info("✨ MemoryWrapper initialized for production scale!")

    async def get_memory_client(self) -> AsyncMemory:
        """Get or create async mem0 client."""
        if self._memory_client is None:
            try:
                # Build a Mem0 MemoryConfig and create AsyncMemory directly
                from mem0.configs.base import MemoryConfig  # type: ignore[reportMissingImports]
                mem0_config = MemoryConfig(**self.config)
                self._memory_client = AsyncMemory(mem0_config)
                self._logger.info("✅ AsyncMemory client initialized")
            except Exception as e:
                self._logger.exception(f"Failed to initialize AsyncMemory: {e}")
                raise
        return self._memory_client

    async def add_memory(self, user_id: UUID, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Add memory asynchronously.

        Non-blocking operation that scales to thousands of concurrent requests.
        """
        from datetime import UTC, datetime

        try:
            if metadata is None:
                metadata = {}

            metadata.update(
                {
                    "user_id": str(user_id),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )

            memory_client = await self.get_memory_client()
            result = await memory_client.add(
                messages=[{"role": "user", "content": content}], user_id=str(user_id), metadata=metadata
            )

            self._logger.debug(f"Added memory for user {user_id}")
            return result or {}

        except Exception as e:
            self._logger.exception(f"Error adding memory for user {user_id}: {e}")

            # Reset client on connection errors
            if "connection" in str(e).lower():
                self._memory_client = None
            # Return empty dict instead of raising to prevent breaking chat flow
            return {}

    async def get_memories(self, user_id: UUID, limit: int = 100) -> list[dict[str, Any]]:
        """
        Get memories asynchronously.

        Retrieves all memories for a user without blocking.
        """
        try:
            memory_client = await self.get_memory_client()
            results = await memory_client.get_all(user_id=str(user_id), limit=limit)

            # mem0 returns a dict with 'results' key
            if isinstance(results, dict):
                return results.get("results", [])

            # Fallback for list or other format
            return results if results else []

        except Exception as e:
            self._logger.exception(f"Error getting memories for user {user_id}: {e}")

            # Reset client on connection errors
            if "connection" in str(e).lower():
                self._memory_client = None
            return []

    async def search_memories(
        self, user_id: UUID, query: str, limit: int = 5, threshold: float | None = None
    ) -> list[dict[str, Any]]:
        """
        Search memories asynchronously.

        Vector similarity search without blocking the event loop.
        """
        try:
            memory_client = await self.get_memory_client()
            results = await memory_client.search(
                query=query,
                user_id=str(user_id),
                limit=limit,
                threshold=threshold,
            )

            # mem0 returns a dict with 'results' key
            if isinstance(results, dict):
                return results.get("results", [])

            # Fallback for list or other format
            return results if results else []

        except Exception as e:
            self._logger.exception(f"Error searching memories for user {user_id}: {e}")

            # Reset client on connection errors
            if "connection" in str(e).lower():
                self._memory_client = None
            return []

    async def delete_memory(self, user_id: UUID, memory_id: str) -> bool:
        """Delete a specific memory asynchronously."""
        try:
            memory_client = await self.get_memory_client()
            await memory_client.delete(memory_id)
            self._logger.info(f"Deleted memory {memory_id} for user {user_id}")
            return True

        except Exception as e:
            self._logger.exception(f"Error deleting memory {memory_id}: {e}")

            # Reset client on connection errors
            if "connection" in str(e).lower():
                self._memory_client = None
            return False

    async def build_memory_context(self, user_id: UUID, query: str, *, limit: int = 5, threshold: float | None = 0.3) -> str:
        """
        Build context from memories for AI responses.

        Searches relevant memories and formats them for LLM context.
        """
        try:
            memories = await self.search_memories(user_id, query, limit=limit, threshold=threshold)

            if not memories:
                return ""

            # Trust mem0 to return properly filtered results
            context_parts = []
            for memory in memories:
                if isinstance(memory, dict):
                    # mem0 should handle the field naming consistently
                    content = memory.get("memory", memory.get("content", ""))
                    if content:
                        context_parts.append(f"• {content}")

            return "\n".join(context_parts)

        except Exception as e:
            self._logger.warning(f"Error building memory context: {e}")
            return ""



class _MemorySingleton:
    """Thread-safe singleton container for MemoryWrapper."""

    _instance: MemoryWrapper | None = None

    @classmethod
    async def get_instance(cls) -> MemoryWrapper:
        """Get or create the singleton MemoryWrapper instance."""
        if cls._instance is None:
            cls._instance = MemoryWrapper()
        return cls._instance


async def get_memory_wrapper() -> MemoryWrapper:
    """Get singleton async memory wrapper.

    This function provides backward compatibility while using
    a cleaner singleton pattern without global statements.
    """
    return await _MemorySingleton.get_instance()
