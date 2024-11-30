from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.database.session import DbSession
from src.roadmaps.dependencies import LimitParam, PageParam
from src.roadmaps.schemas import RoadmapCreate, RoadmapResponse, RoadmapsListResponse, RoadmapUpdate
from src.roadmaps.service import RoadmapService


router = APIRouter(prefix="/api/v1/roadmaps", tags=["roadmaps"])


@router.get(
    "",
    summary="List all roadmaps",
    description="Retrieve a paginated list of roadmaps with optional filtering",
)
async def list_roadmaps(
    session: DbSession,
    search: Annotated[str | None, Query(description="Search term for roadmap title/description")] = None,
    page: PageParam = 1,  # Default set here
    limit: LimitParam = 10,  # Default set here
) -> RoadmapsListResponse:
    """Get a paginated list of roadmaps with optional filtering."""
    service = RoadmapService(session)
    roadmaps, total = await service.get_roadmaps(
        search=search,
        page=page,
        limit=limit,
    )

    return RoadmapsListResponse(
        items=[RoadmapResponse.model_validate(r) for r in roadmaps],
        total=total,
        page=page,
        pages=(total + limit - 1) // limit,
    )

@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create new roadmap",
)
async def create_roadmap(
    data: RoadmapCreate,
    session: DbSession,
) -> RoadmapResponse:
    """Create a new roadmap."""
    service = RoadmapService(session)
    roadmap = await service.create_roadmap(data)
    return RoadmapResponse.model_validate(roadmap)


@router.get(
    "/{roadmap_id}",
    summary="Get roadmap by ID",
)
async def get_roadmap(
    roadmap_id: UUID,
    session: DbSession,
) -> RoadmapResponse:
    """Get a single roadmap by ID."""
    service = RoadmapService(session)
    roadmap = await service.get_roadmap(roadmap_id)
    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found",
        )
    return RoadmapResponse.model_validate(roadmap)


@router.put(
    "/{roadmap_id}",
    summary="Update roadmap",
)
async def update_roadmap(
    roadmap_id: UUID,
    data: RoadmapUpdate,
    session: DbSession,
) -> RoadmapResponse:
    """Update an existing roadmap."""
    service = RoadmapService(session)
    roadmap = await service.update_roadmap(roadmap_id, data)
    if not roadmap:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found",
        )
    return RoadmapResponse.model_validate(roadmap)


@router.delete(
    "/{roadmap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete roadmap",
)
async def delete_roadmap(
    roadmap_id: UUID,
    session: DbSession,
) -> None:
    """Delete a roadmap."""
    service = RoadmapService(session)
    if not await service.delete_roadmap(roadmap_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Roadmap not found",
        )
