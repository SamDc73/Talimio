from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.roadmaps.dependencies import LimitParam, PageParam
from src.roadmaps.models import Node, Roadmap
from src.roadmaps.schemas import (
    NodeCreate,
    NodeResponse,
    NodeStatusUpdate,
    NodeUpdate,
    RoadmapCreate,
    RoadmapResponse,
    RoadmapsListResponse,
    RoadmapUpdate,
)
from src.roadmaps.service import RoadmapService


router = APIRouter(prefix="/api/v1/roadmaps", tags=["roadmaps"])

# Create a separate router for direct node access endpoints
nodes_router = APIRouter(prefix="/api/v1/nodes", tags=["nodes"])


@router.get(
    "",
    summary="List all roadmaps",
    description="Retrieve a paginated list of roadmaps with optional filtering",
)
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
        query = (
            select(Roadmap)
            .options(selectinload(Roadmap.nodes).selectinload(Node.children))
            .where(Roadmap.id == roadmap.id)
        )
        result = await session.execute(query)
        RoadmapResponse.model_validate(result.scalars().first())

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

    # Ensure nodes and their children are loaded before validation
    query = (
        select(Roadmap).options(selectinload(Roadmap.nodes).selectinload(Node.children)).where(Roadmap.id == roadmap.id)
    )
    result = await session.execute(query)
    return RoadmapResponse.model_validate(result.scalars().first())


@router.get(
    "/{roadmap_id}",
    responses={404: {"description": "Roadmap not found"}},
)
async def get_roadmap(
    roadmap_id: UUID,
    session: DbSession,
) -> RoadmapResponse:
    """Get a single roadmap by ID."""
    service = RoadmapService(session)
    try:
        roadmap = await service.get_roadmap(roadmap_id)
        # Ensure relationships are loaded before validation
        query = (
            select(Roadmap)
            .options(selectinload(Roadmap.nodes).selectinload(Node.children))
            .where(Roadmap.id == roadmap.id)
        )
        result = await session.execute(query)
        return RoadmapResponse.model_validate(result.scalars().first())
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.patch(
    "/{roadmap_id}",
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
)
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
)
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
        return NodeResponse.model_validate(node)
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if isinstance(e, ResourceNotFoundError)
            else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.patch(
    "/{roadmap_id}/nodes/{node_id}",
    responses={404: {"description": "Roadmap or node not found"}},
)
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
        return NodeResponse.model_validate(node)
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND
            if isinstance(e, ResourceNotFoundError)
            else status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.delete(
    "/{roadmap_id}/nodes/{node_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"description": "Roadmap or node not found"}},
)
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
)
async def get_node(
    roadmap_id: UUID,
    node_id: UUID,
    session: DbSession,
) -> NodeResponse:
    """Get a single node from a roadmap."""
    service = RoadmapService(session)
    try:
        node = await service.get_node(roadmap_id, node_id)

        def _raise_resource_not_found() -> None:
            msg = "Node"
            raise ResourceNotFoundError(msg, str(node_id))

        if not node:
            _raise_resource_not_found()
        return NodeResponse.model_validate(node)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.post(
    "/{roadmap_id}/nodes/{node_id}/generate-sub-nodes",
    summary="Generate sub-nodes for a node using LLM",
    status_code=status.HTTP_201_CREATED,
)
async def generate_sub_nodes(
    roadmap_id: UUID,
    node_id: UUID,
    session: DbSession,
) -> list[NodeResponse]:
    """Generate sub-nodes for a node using LLM, providing the full roadmap tree as context."""
    service = RoadmapService(session)
    try:
        nodes = await service.generate_sub_nodes(roadmap_id, node_id)
        return [NodeResponse.model_validate(n) for n in nodes]
    except (ResourceNotFoundError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get(
    "/{roadmap_id}/nodes",
    summary="Get all nodes for a roadmap",
    responses={404: {"description": "Roadmap not found"}},
)
async def get_roadmap_nodes(
    roadmap_id: UUID,
    session: DbSession,
) -> list[NodeResponse]:
    """Get all nodes for a roadmap with their current status."""
    service = RoadmapService(session)
    try:
        nodes = await service.get_roadmap_nodes(roadmap_id)
        return [NodeResponse.model_validate(n) for n in nodes]
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


# Phase 2.1: Direct Node Access Endpoints
@nodes_router.get(
    "/{node_id}",
    summary="Get node directly by ID",
    responses={404: {"description": "Node not found"}},
)
async def get_node_direct(
    node_id: UUID,
    session: DbSession,
) -> NodeResponse:
    """Get a node directly by ID without requiring roadmap ID."""
    service = RoadmapService(session)
    try:
        node = await service.get_node_direct(node_id)
        return NodeResponse.model_validate(node)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@nodes_router.patch(
    "/{node_id}",
    summary="Update node directly by ID",
    responses={404: {"description": "Node not found"}},
)
async def update_node_direct(
    node_id: UUID,
    data: NodeUpdate,
    session: DbSession,
) -> NodeResponse:
    """Update a node directly by ID without requiring roadmap ID."""
    service = RoadmapService(session)
    try:
        node = await service.update_node_direct(node_id, data)
        return NodeResponse.model_validate(node)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@nodes_router.put(
    "/{node_id}/status",
    summary="Update node status directly by ID",
    responses={404: {"description": "Node not found"}},
)
async def update_node_status(
    node_id: UUID,
    data: NodeStatusUpdate,
    session: DbSession,
) -> NodeResponse:
    """Update node status directly by ID."""
    service = RoadmapService(session)
    try:
        node = await service.update_node_status(node_id, data.status)
        return NodeResponse.model_validate(node)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
