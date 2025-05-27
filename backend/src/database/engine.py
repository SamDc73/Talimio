from sqlalchemy.ext.asyncio import create_async_engine

from src.config.settings import get_settings


settings = get_settings()

# Create async engine with Neon-optimized settings
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,  # Reduced for Neon
    max_overflow=10,  # Reduced for Neon
    pool_recycle=300,  # Recycle connections every 5 minutes
    pool_timeout=20,  # Timeout for getting connection from pool
    connect_args={
        "server_settings": {"jit": "off"},
        "command_timeout": 60,
        "timeout": 10,  # asyncpg uses 'timeout' not 'connection_timeout'
    },
)
