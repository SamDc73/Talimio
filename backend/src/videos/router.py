from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import get_db_session
from src.videos.schemas import (
    VideoCreate,
    VideoUpdate,
    VideoProgressUpdate,
    VideoResponse,
    VideoListResponse
)
from src.videos.service import video_service

router = APIRouter(prefix="/api/v1/videos", tags=["videos"])


@router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def create_video(
    video_data: VideoCreate,
    db: AsyncSession = Depends(get_db_session)
) -> VideoResponse:
    """Add a YouTube video to the library."""
    try:
        return await video_service.create_video(db, video_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("", response_model=VideoListResponse)
async def list_videos(
    db: AsyncSession = Depends(get_db_session),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    channel: Optional[str] = Query(None, description="Filter by channel name"),
    search: Optional[str] = Query(None, description="Search in title, description, or channel"),
    tags: Optional[List[str]] = Query(None, description="Filter by tags")
) -> VideoListResponse:
    """List all YouTube videos in library with optional filtering."""
    return await video_service.get_videos(db, page=page, size=size, channel=channel, search=search, tags=tags)


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(
    video_id: int,
    db: AsyncSession = Depends(get_db_session)
) -> VideoResponse:
    """Get a specific video by ID."""
    try:
        return await video_service.get_video(db, video_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{video_id}", response_model=VideoResponse)
async def update_video(
    video_id: int,
    update_data: VideoUpdate,
    db: AsyncSession = Depends(get_db_session)
) -> VideoResponse:
    """Update video metadata."""
    try:
        return await video_service.update_video(db, video_id, update_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/{video_id}/progress", response_model=VideoResponse)
async def update_video_progress(
    video_id: int,
    progress_data: VideoProgressUpdate,
    db: AsyncSession = Depends(get_db_session)
) -> VideoResponse:
    """Update video watch progress."""
    try:
        return await video_service.update_progress(db, video_id, progress_data)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/{video_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_video(
    video_id: int,
    db: AsyncSession = Depends(get_db_session)
) -> None:
    """Remove a video from library."""
    try:
        await video_service.delete_video(db, video_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))