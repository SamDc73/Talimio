from sqlalchemy.ext.declarative import declarative_base

from .session import engine


Base = declarative_base()

async def create_all_tables() -> None:
    """Create all tables in the database."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
