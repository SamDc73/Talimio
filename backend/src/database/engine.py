

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.settings import get_settings


settings = get_settings()


def create_app_engine() -> AsyncEngine:
    """Create the async engine optimized for direct Postgres or Supabase pooler.

    - Direct (docker-compose:5432): standard pool with pre-ping.
    - Supabase pooler (pooler.supabase.*:6543): small pool so we don't hog sessions.

    Prepared statements guidance (psycopg3):
    - Direct connections and Supabase session mode support prepared statements.
    - Transaction poolers do NOT. Toggle via settings.DB_DISABLE_PREPARED_STATEMENTS when needed.
    See: Supabase Supavisor FAQ and PgBouncer docs.
    """
    database_url = settings.DATABASE_URL

    # Heuristic: any Supabase pooler URL contains either ".supabase." or ".pooler."
    using_pooler = ".supabase." in database_url or ".pooler." in database_url

    # Optimize pool settings based on connection type
    if using_pooler:
        # Session pooler: keep pool small (each connection holds a backend)
        pool_size = 3
        max_overflow = 2
        pool_recycle = 1800  # ~30m
        pool_pre_ping = True
        connect_args = {"connect_timeout": 10, "prepare_threshold": None}
    else:
        # Direct connection: standard pooling
        pool_size = 10
        max_overflow = 10
        pool_recycle = 3600  # ~1h
        pool_pre_ping = True
        connect_args = {"connect_timeout": 10}

    # Create the engine with optimized settings
    return create_async_engine(
        database_url,
        echo=False,  # Set True for SQL debugging
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
        pool_use_lifo=True,  # Reuse hot connections (beneficial with poolers)
        connect_args=connect_args,
    )



# Create the engine
engine: AsyncEngine = create_app_engine()
