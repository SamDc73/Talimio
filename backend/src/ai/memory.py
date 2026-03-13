
import uuid
from collections.abc import Awaitable, Callable


"""
Simplified async memory manager using mem0's AsyncMemory.

Key design:
- Single initialization -- reuses AsyncMemory client across all calls
- One database source of truth from DATABASE_URL
- Checked psycopg3 connection pool injected into mem0
- Retry once on transient DB connection errors by resetting the memory client
- Proper error handling: best-effort -- memory failures never break the
  primary request flow
"""

import logging
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

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

_MEMORY_POOL_MIN_CONNECTIONS = 1
_MEMORY_POOL_MAX_CONNECTIONS = 3
_MEMORY_DB_MAX_ATTEMPTS = 2


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


def _build_checked_connection_pool(connection_string: str) -> ConnectionPool:
    """Create a psycopg3 pool that validates connections on checkout."""
    return ConnectionPool(
        conninfo=connection_string,
        min_size=_MEMORY_POOL_MIN_CONNECTIONS,
        max_size=_MEMORY_POOL_MAX_CONNECTIONS,
        check=ConnectionPool.check_connection,
        open=True,
    )


def get_memory_client() -> AsyncMemory:
    """Get or create the singleton AsyncMemory client."""
    global _memory_client  # noqa: PLW0603

    if _memory_client is None:
        if not _memory_is_configured():
            # Memory explicitly disabled via missing config; do nothing
            msg = "Memory disabled (MEMORY_* not set)"
            raise RuntimeError(msg)
        pool: ConnectionPool | None = None
        try:
            apply_mem0_litellm_embedder_patch()
            config = _get_memory_config()
            vector_store = config.get("vector_store")
            vector_store_config = vector_store.get("config") if isinstance(vector_store, dict) else None
            if not isinstance(vector_store_config, dict):
                msg = "Invalid mem0 vector store configuration type"
                raise TypeError(msg)
            connection_string = vector_store_config.get("connection_string")
            if not isinstance(connection_string, str):
                msg = "Invalid mem0 vector store connection string type"
                raise TypeError(msg)
            if not connection_string:
                msg = "Missing mem0 vector store connection string"
                raise ValueError(msg)
            pool = _build_checked_connection_pool(connection_string)
            vector_store_config["connection_pool"] = pool
            _memory_client = AsyncMemory(config=MemoryConfig(**config))
            logger.debug("memory.client.initialized")
        except (RuntimeError, TypeError, ValueError, OSError, psycopg.Error):
            if pool is not None:
                try:
                    pool.close()
                except (RuntimeError, OSError, psycopg.Error):
                    logger.exception("memory.init.pool_close_failed")
            logger.exception("memory.init.failed")
            raise

    return _memory_client


async def _run_memory_operation[MemoryResultT](
    *,
    operation: str,
    execute: Callable[[AsyncMemory], Awaitable[MemoryResultT]],
    fallback: MemoryResultT,
) -> MemoryResultT:
    """Execute a mem0 operation and retry once after transient DB failures."""
    for attempt in range(1, _MEMORY_DB_MAX_ATTEMPTS + 1):
        try:
            client = get_memory_client()
            return await execute(client)
        except (TimeoutError, ConnectionError, OSError, psycopg.Error) as error:
            if attempt < _MEMORY_DB_MAX_ATTEMPTS:
                logger.warning(
                    "Memory %s failed with transient DB error on attempt %s/%s: %s",
                    operation,
                    attempt,
                    _MEMORY_DB_MAX_ATTEMPTS,
                    error,
                )
                cleanup_memory_client()
                continue
            logger.warning("Memory %s failed after retry: %s", operation, error)
            return fallback
        except (RuntimeError, TypeError, ValueError, AttributeError) as error:
            logger.warning("Memory %s failed with non-transient error: %s", operation, error, exc_info=True)
            return fallback

    return fallback


async def add_memory(
    user_id: uuid.UUID,
    messages: str | dict[str, Any] | list[dict[str, Any]],
    metadata: dict[str, Any] | None = None,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Add memory for a user."""
    if not _memory_is_configured():
        return {}

    async def _execute(client: AsyncMemory) -> dict[str, Any]:
        result = await client.add(
            messages=messages,
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
            metadata=metadata,
        )
        logger.debug("Added memory for user %s", user_id)
        return result or {}

    return await _run_memory_operation(
        operation=f"add for user {user_id}",
        execute=_execute,
        fallback={},
    )


async def get_memories(
    user_id: uuid.UUID,
    limit: int = 100,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get all memories for a user."""
    if not _memory_is_configured():
        return []

    async def _execute(client: AsyncMemory) -> list[dict[str, Any]]:
        results = await client.get_all(
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
            limit=limit,
        )

        if isinstance(results, dict):
            return results.get("results", [])
        return []

    return await _run_memory_operation(
        operation=f"get all for user {user_id}",
        execute=_execute,
        fallback=[],
    )


async def search_memories(
    user_id: uuid.UUID,
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

    async def _execute(client: AsyncMemory) -> list[dict[str, Any]]:
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

    return await _run_memory_operation(
        operation=f"search for user {user_id}",
        execute=_execute,
        fallback=[],
    )


async def delete_memory(user_id: uuid.UUID, memory_id: str) -> bool:
    """Delete a specific memory."""
    if not _memory_is_configured():
        return False

    async def _execute(client: AsyncMemory) -> bool:
        existing_memory = await client.get(memory_id)
        if existing_memory is None:
            logger.info("Memory %s not found for user %s", memory_id, user_id)
            return False
        try:
            await client.delete(memory_id)
        except AttributeError:
            logger.warning(
                "Memory provider failed to delete memory %s for user %s; treating as missing memory",
                memory_id,
                user_id,
                exc_info=True,
            )
            return False
        logger.info("Deleted memory %s for user %s", memory_id, user_id)
        return True

    return await _run_memory_operation(
        operation=f"delete memory {memory_id}",
        execute=_execute,
        fallback=False,
    )


async def delete_all_memories(
    user_id: uuid.UUID,
    *,
    agent_id: str | None = None,
    run_id: str | None = None,
) -> bool:
    """Delete all memories for a user (optionally scoped by agent/run)."""
    if not _memory_is_configured():
        return True

    async def _execute(client: AsyncMemory) -> bool:
        await client.delete_all(
            user_id=str(user_id),
            agent_id=agent_id,
            run_id=run_id,
        )
        logger.info("Cleared memories for user %s", user_id)
        return True

    return await _run_memory_operation(
        operation=f"clear all for user {user_id}",
        execute=_execute,
        fallback=False,
    )


def cleanup_memory_client() -> None:
    """Cleanup the memory client on shutdown."""
    global _memory_client  # noqa: PLW0603

    client = _memory_client
    if client is None:
        return

    _memory_client = None
    cleanup_errors: list[Exception] = []

    for store_attr in ("vector_store", "_telemetry_vector_store"):
        store = getattr(client, store_attr, None)
        pool = getattr(store, "connection_pool", None) if store is not None else None
        if pool is None:
            continue

        close_pool = getattr(pool, "close", None)
        close_all = getattr(pool, "closeall", None)
        try:
            if callable(close_pool):
                close_pool()
            elif callable(close_all):
                close_all()
        except Exception as error:
            logger.exception("memory.cleanup.pool_close_failed")
            cleanup_errors.append(error)

    try:
        from mem0.memory import telemetry as mem0_telemetry

        mem0_client = getattr(mem0_telemetry, "client_telemetry", None)
        close_client = getattr(mem0_client, "close", None) if mem0_client is not None else None
        if callable(close_client):
            close_client()
    except ImportError:
        logger.debug("memory.cleanup.telemetry_module_missing")
    except Exception as error:
        logger.exception("memory.cleanup.telemetry_close_failed")
        cleanup_errors.append(error)

    if cleanup_errors:
        message = "Memory cleanup failed"
        raise RuntimeError(message) from cleanup_errors[0]

    logger.debug("memory.cleanup.completed")


def warm_memory_client() -> bool:
    """Initialize the AsyncMemory client so the first request skips cold start."""
    if not _memory_is_configured():
        logger.debug("memory.warmup.skipped")
        return False
    get_memory_client()
    return True
