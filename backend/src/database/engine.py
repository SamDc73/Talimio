from sqlalchemy.ext.asyncio import create_async_engine

from src.config.settings import get_settings


settings = get_settings()

# Create async engine with SSL requirements for Tembo
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    ssl=True,  # Enable SSL for Tembo.io connection
)
