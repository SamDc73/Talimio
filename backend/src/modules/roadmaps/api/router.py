from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ..application.services import RoadmapService
from .dependencies import LimitParam, PageParam, get_db_session
from .schemas import RoadmapCreate, RoadmapResponse, RoadmapsListResponse, RoadmapUpdate


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
    service = RoadmapService(session)
    roadmaps, total = await service.get_roadmaps(
        user_id=user_id,
        search=search,
        page=page,
        limit=limit,
    )

    return RoadmapsListResponse(
        items=[RoadmapResponse.from_orm(r) for r in roadmaps],
        total=total,
        page=page,
        pages=(total + limit - 1) // limit,
    )


@router.post(
    "",
    response_model=RoadmapResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new roadmap",
)
async def create_roadmap(
    data: RoadmapCreate,
    session: AsyncSession = Depends(get_db_session),
) -> RoadmapResponse:
    """Create a new roadmap."""
    service = RoadmapService(session)
    roadmap = await service.create_roadmap(data)
    return RoadmapResponse.from_orm(roadmap)


@router.get(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    summary="Get roadmap by ID",
)
async def get_roadmap(
    roadmap_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RoadmapResponse:
    """Get a single roadmap by ID."""
    service = RoadmapService(session)
    roadmap = await service.get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found",
        )
    return RoadmapResponse.from_orm(roadmap)


@router.put(
    "/{roadmap_id}",
    response_model=RoadmapResponse,
    summary="Update roadmap",
)
async def update_roadmap(
    roadmap_id: UUID,
    data: RoadmapUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> RoadmapResponse:
    """Update an existing roadmap."""
    service = RoadmapService(session)
    roadmap = await service.update_roadmap(roadmap_id, data)
    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found",
        )
    return RoadmapResponse.from_orm(roadmap)


@router.delete(
    "/{roadmap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete roadmap",
)
async def delete_roadmap(
    roadmap_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Delete a roadmap."""
    service = RoadmapService(session)
    if not await service.delete_roadmap(roadmap_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found",
        )
