from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.roadmaps.dependencies import LimitParam, PageParam
from src.roadmaps.schemas import (
    NodeCreate,
    NodeResponse,
    NodeUpdate,
    RoadmapCreate,
    RoadmapResponse,
    RoadmapsListResponse,
    RoadmapUpdate,
)
from src.roadmaps.service import RoadmapService


router = APIRouter(prefix="/api/v1/roadmaps", tags=["roadmaps"])


@router.get(
    "",
    summary="List all roadmaps",
    description="Retrieve a paginated list of roadmaps with optional filtering",
)  # type: ignore[misc]
async def list_roadmaps(
    session: DbSession,
    search: Annotated[str | None, Query(description="Search term for roadmap title/description")] = None,
    page: PageParam = 1,
    limit: LimitParam = 10,
) -> RoadmapsListResponse:
    """Get a paginated list of roadmaps with optional filtering."""
    service = RoadmapService(session)
    roadmaps, total = await service.get_roadmaps(
        search=search,
        page=page,
        limit=limit,
    )
    
    # Ensure relationships are loaded before validation
    for roadmap in roadmaps:
        await session.refresh(roadmap, ["nodes"])
        for node in roadmap.nodes:
            await session.refresh(node, ["prerequisites"])

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
)  # type: ignore[misc]
async def create_roadmap(
    data: RoadmapCreate,
    session: DbSession,
) -> RoadmapResponse:
    """Create a new roadmap."""
    service = RoadmapService(session)
    roadmap = await service.create_roadmap(data)
    
    # Ensure nodes are loaded before validation
    await session.refresh(roadmap, ["nodes"])
    return RoadmapResponse.model_validate(roadmap)


@router.get(
    "/{roadmap_id}",
    responses={404: {"description": "Roadmap not found"}},
)  # type: ignore[misc]
async def get_roadmap(
    roadmap_id: UUID,
    session: DbSession,
) -> RoadmapResponse:
    """Get a single roadmap by ID."""
    service = RoadmapService(session)
    try:
        roadmap = await service.get_roadmap(roadmap_id)
        # Ensure relationships are loaded before validation
        await session.refresh(roadmap, ["nodes"])
        for node in roadmap.nodes:
            await session.refresh(node, ["prerequisites"])
        return RoadmapResponse.model_validate(roadmap)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.put(
    "/{roadmap_id}",
)  # type: ignore[misc]
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
    return cast(RoadmapResponse, RoadmapResponse.model_validate(roadmap))

@router.delete(
    "/{roadmap_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)  # type: ignore[misc]
async def delete_roadmap(
    roadmap_id: UUID,
    session: DbSession,
) -> None:
    """Delete a roadmap."""
    service = RoadmapService(session)
    try:
        await service.delete_roadmap(roadmap_id)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{roadmap_id}/nodes",
    status_code=status.HTTP_201_CREATED,
    responses={404: {"description": "Roadmap not found"}},
)  # type: ignore[misc]
async def create_node(
    roadmap_id: UUID,
    data: NodeCreate,
    session: DbSession,
) -> NodeResponse:
    """Create a new node in a roadmap."""
    if data.roadmap_id != roadmap_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Roadmap ID in path must match roadmap_id in request body",
        )
    
    service = RoadmapService(session)
    try:
        node = await service.create_node(roadmap_id, data)
        await session.refresh(node, ["prerequisites"])
        return NodeResponse.model_validate(node)
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if isinstance(e, ResourceNotFoundError) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.put(
    "/{roadmap_id}/nodes/{node_id}",
    responses={404: {"description": "Roadmap or node not found"}},
)  # type: ignore[misc]
async def update_node(
    roadmap_id: UUID,
    node_id: UUID,
    data: NodeUpdate,
    session: DbSession,
) -> NodeResponse:
    """Update a node in a roadmap."""
    service = RoadmapService(session)
    try:
        node = await service.update_node(roadmap_id, node_id, data)
        await session.refresh(node, ["prerequisites"])
        return NodeResponse.model_validate(node)
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND if isinstance(e, ResourceNotFoundError) else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete(
    "/{roadmap_id}/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Roadmap or node not found"}},
)  # type: ignore[misc]
async def delete_node(
    roadmap_id: UUID,
    node_id: UUID,
    session: DbSession,
) -> None:
    """Delete a node from a roadmap."""
    service = RoadmapService(session)
    try:
        await service.delete_node(roadmap_id, node_id)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/{roadmap_id}/nodes/{node_id}",
    responses={404: {"description": "Roadmap or node not found"}},
)  # type: ignore[misc]
async def get_node(
    roadmap_id: UUID,
    node_id: UUID,
    session: DbSession,
) -> NodeResponse:
    """Get a single node from a roadmap."""
    service = RoadmapService(session)
    try:
        node = await service._get_node(roadmap_id, node_id)
        if not node:
            raise ResourceNotFoundError("Node", str(node_id))
        await session.refresh(node, ["prerequisites"])
        return NodeResponse.model_validate(node)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
