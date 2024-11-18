from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.queries import get_roadmaps
from .dependencies import LimitParam, PageParam, get_db_session
from .schemas import RoadmapResponse, RoadmapsListResponse


router = APIRouter(prefix="/api/v1/roadmaps", tags=["roadmaps"])

@router.get(
    "",
    response_model=RoadmapsListResponse,
    summary="List all roadmaps",
    description="Retrieve a paginated list of roadmaps with optional filtering",
)
async def list_roadmaps(
    session: AsyncSession = Depends(get_db_session),
    user_id: UUID | None = Query(None, description="Filter roadmaps by user"),
    search: str | None = Query(None, description="Search term for roadmap title/description"),
    page: PageParam = 1,
    limit: LimitParam = 10,
) -> RoadmapsListResponse:
    """Get a paginated list of roadmaps with optional filtering."""
    roadmaps, total = await get_roadmaps(
        session,
        user_id=user_id,
        search=search,
        page=page,
        limit=limit,
    )

    # Calculate total pages
    total_pages = (total + limit - 1) // limit

    return RoadmapsListResponse(
        items=[
            RoadmapResponse(
                id=roadmap.id,
                title=roadmap.title,
                description=roadmap.description,
                skill_level=roadmap.skill_level,
                created_at=roadmap.created_at,
                updated_at=roadmap.updated_at,
            )
            for roadmap in roadmaps
        ],
        total=total,
        page=page,
        pages=total_pages,
    )
