"""Simplified database initialization - creates extensions and tables."""

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.auth.config import DEFAULT_USER_ID

# Import all models to register them with Base metadata
from src.books.models import *  # noqa: F403
from src.config import env
from src.courses.models import *  # noqa: F403
from src.tagging.models import *  # noqa: F403
from src.user.models import *  # noqa: F403
from src.videos.models import *  # noqa: F403

from .base import Base
from .engine import engine


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def init_database(db_engine: AsyncEngine) -> None:
    """Initialize database with required extensions and create all tables."""
    async with db_engine.begin() as conn:
        # Clean any stale prepared statements before metadata operations
        # This prevents "prepared statement already exists" errors during startup
        await conn.exec_driver_sql("DEALLOCATE ALL")

        # 1. Enable required extensions
        logger.info("Enabling required PostgreSQL extensions...")

        # Enable UUID generation
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        logger.info("uuid-ossp extension enabled")

        # Enable pgvector for embeddings - CRITICAL for RAG system
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            logger.info("pgvector extension enabled")
        except Exception as e:
            logger.exception(f"Failed to enable pgvector extension: {e}")
            logger.exception("Make sure pgvector is installed in your PostgreSQL instance")
            logger.exception("For installation instructions, see: https://github.com/pgvector/pgvector")
            raise

        # Enable pg_trgm for text search (optional but useful)
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        logger.info("pg_trgm extension enabled for text search")

        # 2. Create all tables from models
        logger.info("Creating database tables from models...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("All tables created successfully")

        # 3. Create default user if needed (for self-hosters with AUTH_PROVIDER=none)
        logger.info("Ensuring default user exists...")
        await _ensure_default_user(conn)

        # 4. Ensure mem0 vector store indexes exist
        logger.info("Ensuring mem0 vector indexes exist...")
        await _ensure_vector_indexes(conn)

        logger.info("Database initialization completed successfully")


async def _ensure_default_user(conn: AsyncConnection) -> None:
    """Create default user for self-hosters (AUTH_PROVIDER=none)."""
    try:
        # Check if users table exists
        result = await conn.execute(
            text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = 'users'
            )
        """)
        )
        table_exists = result.scalar()

        if table_exists:
            # Check if default user already exists
            result = await conn.execute(
                text("SELECT COUNT(*) FROM users WHERE id = :id"),
                {"id": str(DEFAULT_USER_ID)}
            )
            user_exists = result.scalar() > 0

            if not user_exists:
                # Create default user for self-hosters
                await conn.execute(
                    text("""
                    INSERT INTO users (id, username, email, password_hash, role, is_active, created_at, updated_at)
                    VALUES (:id, 'default', 'user@localhost', 'not_used_in_single_user_mode', 'user', true, NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                """),
                    {"id": str(DEFAULT_USER_ID)},
                )
                logger.info(f"Created default user for self-hosters with ID: {DEFAULT_USER_ID}")
            else:
                logger.info("Default user already exists")
        else:
            logger.info("Users table doesn't exist yet, will be created by SQLAlchemy")
    except Exception as e:
        logger.warning(f"Could not create default user (non-critical for single-user mode): {e}")


async def _ensure_vector_indexes(conn: AsyncConnection) -> None:
    """Ensure mem0 learning_memories table and HNSW index exist."""
    dims_value = env("MEMORY_EMBEDDING_OUTPUT_DIM", 1536)
    try:
        embedding_dims = int(dims_value) if dims_value is not None else 1536
    except (TypeError, ValueError):
        embedding_dims = 1536
    if embedding_dims <= 0:
        embedding_dims = 1536

    try:
        # Mirrors mem0's pgvector schema (Context7: /mem0ai/mem0 components/vectordbs/dbs/pgvector)
        await conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS public.learning_memories (
                    id UUID PRIMARY KEY,
                    vector vector({embedding_dims}),
                    payload JSONB
                )
                """
            )
        )

        # Remove legacy indexes so the dedicated lm_vec_cos index stays canonical
        for idx_name in ("learning_memories_hnsw_idx", "learning_memories_diskann_idx"):
            await conn.execute(text(f"DROP INDEX IF EXISTS public.{idx_name}"))

        await conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS lm_vec_cos
                ON public.learning_memories
                USING hnsw (vector vector_cosine_ops)
                """
            )
        )
        await conn.execute(text("ANALYZE public.learning_memories"))
        logger.info("Mem0 learning_memories table and HNSW index verified")
    except Exception as exc:  # pragma: no cover - database specific
        logger.exception(f"Failed to ensure mem0 vector indexes: {exc}")
        raise


async def main() -> None:
    """Run the initialization."""
    try:
        await init_database(engine)
        logger.info("Database initialization completed!")
    except Exception:
        logger.exception("Database initialization failed")
        raise


if __name__ == "__main__":
    asyncio.run(main())
