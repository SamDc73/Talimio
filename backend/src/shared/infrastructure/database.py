from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
from src.config.database import db_settings


# Load environment variables from .env file
load_dotenv()

# Create an asynchronous engine with the asyncpg driver
engine = create_async_engine(db_settings.DATABASE_URL, echo=True)

# Create an asynchronous sessionmaker
AsyncSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

# Create a declarative base for ORM models
Base = declarative_base()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session
