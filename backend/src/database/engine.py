from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool, QueuePool

from src.config.settings import get_settings


settings = get_settings()

# Detect PgBouncer (port 6543 = transaction pooler)
use_pgbouncer = ":6543" in settings.DATABASE_URL

# Clean configuration - no workarounds needed
if use_pgbouncer:
    # With PgBouncer, use NullPool (no client-side pooling)
    # and disable prepared statements for compatibility
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
        pool_pre_ping=True,
        echo=settings.DEBUG,
        connect_args={
            "prepare_threshold": None,  # Disable prepared statements for PgBouncer
        }
    )
else:
    # Without PgBouncer, use QueuePool with connection pooling
    engine: AsyncEngine = create_async_engine(
        settings.DATABASE_URL,
        poolclass=QueuePool,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=3600,
        echo=settings.DEBUG,
    )