"""
Simplified async memory manager using mem0's AsyncMemory.

Key optimizations:
- Single initialization - reuses AsyncMemory client across all calls
- Let mem0 handle all connection pooling internally
- Minimal wrapper - rely on mem0's built-in features
- Proper error handling without breaking the flow
"""

import logging
from contextlib import suppress
from typing import Any
from uuid import UUID

from src.ai.mem0_telemetry_disable_patch import apply_mem0_telemetry_disable_patch


apply_mem0_telemetry_disable_patch()

from mem0 import AsyncMemory
from mem0.configs.base import MemoryConfig


apply_mem0_telemetry_disable_patch()

from src.ai.mem0_litellm_embedder_patch import apply_mem0_litellm_embedder_patch
from src.config import env
from src.config.settings import get_settings


logger = logging.getLogger(__name__)

# Module-level instance - initialized once at startup
_memory_client: AsyncMemory | None = None


def _memory_is_configured() -> bool:
    """Return True if required MEMORY_* vars are set."""
    return bool(env("MEMORY_LLM_MODEL") and env("MEMORY_EMBEDDING_MODEL"))


def _resolve_embedding_dims() -> int | None:
    """Return configured embedding dimension, if provided."""
    raw_value = env("MEMORY_EMBEDDING_OUTPUT_DIM")
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError) as exc:
        msg = "MEMORY_EMBEDDING_OUTPUT_DIM must be an integer"
        raise ValueError(msg) from exc


def _get_memory_config() -> dict[str, Any]:
    """Build mem0 configuration from environment."""
    settings = get_settings()

    # mem0 expects a plain postgresql:// URL even when the app uses SQLAlchemy's
    # postgresql+psycopg:// DSN. Keep this conversion local to mem0 only.
    database_url = settings.DATABASE_URL
    if database_url.startswith("postgresql+psycopg://"):
        connection_string = database_url.replace("postgresql+psycopg://", "postgresql://")
    elif database_url.startswith("postgresql://"):
        connection_string = database_url
    else:
        msg = f"Unsupported DATABASE_URL format: {database_url}"
        raise ValueError(msg)

    embedding_dims = _resolve_embedding_dims()

    vector_store_config: dict[str, Any] = {
        "connection_string": connection_string,
        "collection_name": "learning_memories",
        "minconn": 1,
        "maxconn": 3,
    }
    if embedding_dims is not None:
        vector_store_config["embedding_model_dims"] = embedding_dims

    return {
        "vector_store": {
            "provider": "pgvector",
            "config": vector_store_config,
        },
        "llm": {
            "provider": "litellm",
            "config": {
                "model": env("MEMORY_LLM_MODEL"),
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": env("MEMORY_EMBEDDING_MODEL"),
            },
        },
    }


async def get_memory_client() -> AsyncMemory:
    """Get or create the singleton AsyncMemory client."""
    global _memory_client  # noqa: PLW0603

    if _memory_client is None:
        if not _memory_is_configured():
            # Memory explicitly disabled via missing config; do nothing
            msg = "Memory disabled (MEMORY_* not set)"
            raise RuntimeError(msg)
        try:
            apply_mem0_litellm_embedder_patch()
            config = _get_memory_config()
            _memory_client = AsyncMemory(config=MemoryConfig(**config))
            logger.info("AsyncMemory client initialized with connection pooling")
        except Exception:
            logger.exception("Failed to initialize AsyncMemory")
            raise

    return _memory_client


async def add_memory(
    user_id: UUID,
    messages: str | dict[str, Any] | list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Add memory for a user."""
    if not _memory_is_configured():
        return {}
    try:
        client = await get_memory_client()

        # Add memory using mem0's async method
        result = await client.add(
            messages=messages,
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata,
        )

        logger.debug(f"Added memory for user {user_id}")
        return result or {}

    except Exception as e:
        logger.warning(f"Failed to add memory for user {user_id}: {e}")
        return {}  # Don't break the flow


async def get_memories(
    user_id: UUID,
    limit: int = 100,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get all memories for a user."""
    if not _memory_is_configured():
        return []
    try:
        client = await get_memory_client()
        results = await client.get_all(
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
            limit=limit,
        )

        if isinstance(results, dict):
            return results.get("results", [])
        return []

    except Exception as e:
        logger.warning(f"Failed to get memories for user {user_id}: {e}")
        return []


async def search_memories(
    user_id: UUID,
    query: str,
    limit: int = 100,
    threshold: float | None = None,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Search memories for a user."""
    if not _memory_is_configured():
        return []
    if not query or not query.strip():
        return []

    try:
        client = await get_memory_client()
        results = await client.search(
            query=query,
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
            limit=limit,
            threshold=threshold,
        )

        if isinstance(results, dict):
            return results.get("results", [])
        return []

    except Exception as e:
        logger.warning(f"Memory search failed for user {user_id}: {e}")
        return []


async def delete_memory(user_id: UUID, memory_id: str) -> bool:
    """Delete a specific memory."""
    if not _memory_is_configured():
        return False
    try:
        client = await get_memory_client()
        await client.delete(memory_id)
        logger.info(f"Deleted memory {memory_id} for user {user_id}")
        return True

    except Exception as e:
        logger.warning(f"Failed to delete memory {memory_id}: {e}")
        return False


async def delete_all_memories(
    user_id: UUID,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    """Delete all memories for a user (optionally scoped by agent/run)."""
    if not _memory_is_configured():
        return True
    try:
        client = await get_memory_client()
        await client.delete_all(
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
        )
        logger.info(f"Cleared memories for user {user_id}")
        return True
    except Exception as e:
        logger.warning(f"Failed to clear memories for user {user_id}: {e}")
        return False


async def cleanup_memory_client() -> None:
    """Cleanup the memory client on shutdown."""
    global _memory_client  # noqa: PLW0603

    client = _memory_client
    if client is None:
        return

    _memory_client = None

    for store_attr in ("vector_store", "_telemetry_vector_store"):
        store = getattr(client, store_attr, None)
        pool = getattr(store, "connection_pool", None) if store is not None else None
        if pool is None:
            continue

        close_pool = getattr(pool, "close", None)
        close_all = getattr(pool, "closeall", None)
        with suppress(Exception):
            if callable(close_pool):
                close_pool()
            elif callable(close_all):
                close_all()

    with suppress(Exception):
        from mem0.memory import telemetry as mem0_telemetry

        mem0_client = getattr(mem0_telemetry, "client_telemetry", None)
        close_client = getattr(mem0_client, "close", None) if mem0_client is not None else None
        if callable(close_client):
            close_client()

    logger.info("Memory client cleaned up")


async def warm_memory_client() -> None:
    """Initialize the AsyncMemory client so the first request skips cold start."""
    if not _memory_is_configured():
        logger.info("Memory disabled; skipping warm-up")
        return
    await get_memory_client()
