from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.modules.roadmaps.domain.models import Roadmap


async def get_roadmaps(
    session: AsyncSession,
    *,
    user_id: UUID | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> tuple[list[Roadmap], int]:
    """
    Get a paginated list of roadmaps with optional filtering.

    Args:
        session: Database session
        user_id: Optional user ID to filter roadmaps
        search: Optional search term for title/description
        page: Page number (1-based)
        limit: Number of items per page

    Returns
    -------
        Tuple of (list of roadmaps, total count)
    """
    query = select(Roadmap)

    # Apply filters
    if user_id:
        # Note: This would need proper user-roadmap relationship
        # query = query.filter(Roadmap.user_id == user_id)
        pass

    if search:
        query = query.filter(
            Roadmap.title.ilike(f"%{search}%") |
            Roadmap.description.ilike(f"%{search}%"),
        )

    # Get total count
    count_query = select(select(Roadmap).filter(*query.whereclause.args).exists())
    result = await session.execute(count_query)
    total = await session.scalar(select(func.count()).select_from(query))

    # Apply pagination
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)

    # Execute query
    result = await session.execute(query)
    roadmaps = result.scalars().all()

    return roadmaps, total
