from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.engine import engine


async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get an async database session generator.

    Yields
    ------
        AsyncSession: Database session without automatic commit.
        The service layer should handle commits/rollbacks.
    """
    async with async_session_maker() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# Create a reusable dependency
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
