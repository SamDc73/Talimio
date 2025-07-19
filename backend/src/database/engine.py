from sqlalchemy.ext.asyncio import create_async_engine

from src.config.settings import get_settings


settings = get_settings()

# Configure connection args based on database type
connect_args = {}
if "sqlite" in settings.DATABASE_URL:
    # SQLite-specific settings
    connect_args = {
        "check_same_thread": False,
    }
elif "postgresql" in settings.DATABASE_URL:
    # PostgreSQL/Neon-specific settings
    connect_args = {
        "server_settings": {"jit": "off"},
        "command_timeout": 60,
        "timeout": 10,
    }

# Create async engine with appropriate settings
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_recycle=300,
    pool_timeout=20,
    connect_args=connect_args,
)
