
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from src.config.settings import get_settings


settings = get_settings()


def create_app_engine() -> AsyncEngine:
    """Create the async engine optimized for Direct connection or Session pooler.

    Both connection types work on port 5432. Session pooler maintains connection
    state across requests within a session, allowing prepared statements to work.
    """
    # Detect if we're using Supabase session pooler (vs direct connection)
    database_url = settings.DATABASE_URL
    using_session_pooler = ".supabase." in database_url or ".pooler." in database_url

    # Optimize pool settings based on connection type
    if using_session_pooler:
        # Session pooler: Keep pool small since each connection holds a backend
        pool_size = 3  # Small pool for session pooler
        max_overflow = 2  # Minimal overflow
        pool_recycle = 1800  # 30 minutes - before pooler idle timeout
        pool_pre_ping = False  # Not needed with good recycle settings
    else:
        # Direct connection: Standard pooling
        pool_size = 10
        max_overflow = 10
        pool_recycle = 3600  # 1 hour
        pool_pre_ping = True  # Useful for direct connections

    # Create the engine with optimized settings
    engine = create_async_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=pool_pre_ping,
        pool_use_lifo=True,  # Reuse hot connections (better for poolers)
        connect_args={
            # Client-side settings that always work
            "prepare_threshold": 5,  # Prepare after 5 executions (client-side)
            "connect_timeout": 10,  # Fast failure on connection attempts
            # Note: Server settings like statement_timeout are controlled by 
            # Session pooler and cannot be overridden via connection string
        },
    )

    # Clean stale prepared statements on new connections
    # This prevents "prepared statement already exists" errors
    @event.listens_for(engine.sync_engine, "connect")
    def clean_prepared_statements(dbapi_conn, conn_record) -> None:
        """Clean any stale prepared statements from previous app instances."""
        try:
            cursor = dbapi_conn.cursor()
            cursor.execute("DEALLOCATE ALL")
            cursor.close()
        except Exception:
            # Ignore errors - this is just cleanup
            pass

    return engine


# Create the engine
engine: AsyncEngine = create_app_engine()
