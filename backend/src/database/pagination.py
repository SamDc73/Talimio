from typing import TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession


T = TypeVar("T")


class Paginator:
    """Helper class for handling pagination."""

    def __init__(self, page: int = 1, limit: int = 10) -> None:
        self.page = page
        self.limit = limit
        self.offset = (page - 1) * limit

    async def paginate(self, session: AsyncSession, query: Select[tuple[T]]) -> tuple[list[T], int]:
        """
        Paginate a query and return items with total count.

        Parameters
        ----------
        session : AsyncSession
            Database session
        query : Select
            Base query to paginate

        Returns
        -------
        tuple[list[T], int]
            List of items and total count
        """
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total = await session.scalar(count_query) or 0

        # Get paginated items
        paginated_query = query.offset(self.offset).limit(self.limit)
        result = await session.execute(paginated_query)
        items = result.scalars().all()

        return list(items), total
