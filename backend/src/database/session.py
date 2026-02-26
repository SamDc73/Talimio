from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.engine import engine


async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    """Get an async database session generator.

    Yields
    ------
        AsyncSession: Database session with request-scoped commit/rollback.
    """
    async with async_session_maker() as session:
        try:
            yield session
        except SQLAlchemyError:
            await session.rollback()
            raise
        else:
            await session.commit()


# Create a reusable dependency
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
