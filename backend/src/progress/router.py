from typing import Annotated, cast
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from src.core.exceptions import ResourceNotFoundError, ValidationError
from src.database.session import DbSession
from src.progress.schemas import ProgressCreate, ProgressResponse, ProgressUpdate
from src.progress.service import ProgressService


router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


@router.post(
    "/node/{node_id}",
    response_model_exclude_none=True,
)
async def update_node_progress(
    node_id: UUID,
    session: DbSession,
    node_status: Annotated[str, Query(regex="^(not_started|in_progress|completed)$")],
    user_id: Annotated[UUID | None, Query()] = None,
) -> ProgressResponse:
    """Update or create progress for a node."""
    service = ProgressService(session)
    try:
        # Create progress data
        if not user_id:
            msg = "user_id is required"
            raise ValidationError(msg)

        data = ProgressCreate(node_id=node_id, status=node_status, user_id=user_id)
        progress = await service.create_progress(data)
        return cast("ProgressResponse", ProgressResponse.model_validate(progress))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model_exclude_none=True,
)
async def create_progress(
    data: ProgressCreate,
    session: DbSession,
) -> ProgressResponse:
    """Create new progress record."""
    service = ProgressService(session)
    try:
        progress = await service.create_progress(data)
        return cast("ProgressResponse", ProgressResponse.model_validate(progress))
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/{progress_id}",
    response_model_exclude_none=True,
)
async def get_progress(
    progress_id: UUID,
    session: DbSession,
) -> ProgressResponse:
    """Get progress by ID."""
    service = ProgressService(session)
    try:
        progress = await service.get_progress(progress_id)
        return cast("ProgressResponse", ProgressResponse.model_validate(progress))
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.get(
    "/user/{user_id}",
    response_model_exclude_none=True,
)
async def get_user_progress(
    user_id: UUID,
    session: DbSession,
    page: Annotated[int, Query(description="Page number", ge=1)] = 1,
    limit: Annotated[int, Query(description="Items per page", ge=1, le=100)] = 10,
) -> list[ProgressResponse]:
    """Get all progress for a user."""
    service = ProgressService(session)
    try:
        progress_records, total = await service.get_user_progress(
            user_id,
            page=page,
            limit=limit,
        )
        return [cast("ProgressResponse", ProgressResponse.model_validate(p)) for p in progress_records]
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e


@router.get(
    "/user/{user_id}/node/{node_id}",
    response_model_exclude_none=True,
)
async def get_user_node_progress(
    user_id: UUID,
    node_id: UUID,
    session: DbSession,
) -> ProgressResponse:
    """Get progress for a specific user and node."""
    service = ProgressService(session)
    try:
        progress = await service.get_progress_by_user_and_node(user_id, node_id)
        return cast("ProgressResponse", ProgressResponse.model_validate(progress))
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e


@router.put(
    "/{progress_id}",
    response_model_exclude_none=True,
)
async def update_progress(
    progress_id: UUID,
    data: ProgressUpdate,
    session: DbSession,
) -> ProgressResponse:
    """Update progress."""
    service = ProgressService(session)
    try:
        progress = await service.update_progress(progress_id, data)
        return cast("ProgressResponse", ProgressResponse.model_validate(progress))
    except (ResourceNotFoundError, ValidationError) as e:
        status_code = status.HTTP_404_NOT_FOUND if isinstance(e, ResourceNotFoundError) else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=str(e),
        ) from e


@router.delete(
    "/{progress_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_progress(
    progress_id: UUID,
    session: DbSession,
) -> None:
    """Delete progress record."""
    service = ProgressService(session)
    try:
        await service.delete_progress(progress_id)
    except ResourceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e
