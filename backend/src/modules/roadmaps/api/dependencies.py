from typing import Annotated

from fastapi import Query
from sqlalchemy.ext.asyncio import AsyncSession
from src.shared.infrastructure.database import AsyncSessionLocal


async def get_db_session() -> AsyncSession:
    """Get database session."""
    async with AsyncSessionLocal() as session:
        yield session

# Pagination parameters
PageParam = Annotated[int, Query(ge=1)]
LimitParam = Annotated[int, Query(ge=1, le=100)]
