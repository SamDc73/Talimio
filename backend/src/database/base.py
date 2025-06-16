from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all database models."""


async def create_all_tables() -> None:
    """Create all tables in the database."""
    from .engine import engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
