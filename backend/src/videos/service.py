import json
import logging
from typing import List, Optional, Dict, Any

import yt_dlp
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.videos.models import Video
from src.videos.schemas import VideoCreate, VideoUpdate, VideoProgressUpdate, VideoListResponse, VideoResponse
from src.database.pagination import Paginator

logger = logging.getLogger(__name__)


class VideoService:
    """Service for managing videos."""
    
    async def create_video(self, db: AsyncSession, video_data: VideoCreate) -> VideoResponse:
        """Create a new video by fetching metadata from YouTube."""
        # Extract video info using yt-dlp
        video_info = await self._fetch_video_info(video_data.url)
        
        # Check if video already exists
        existing = await db.execute(
            select(Video).where(Video.youtube_id == video_info["youtube_id"])
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Video with ID {video_info['youtube_id']} already exists")
        
        # Create video record
        video = Video(
            youtube_id=video_info["youtube_id"],
            url=video_info["url"],
            title=video_info["title"],
            channel=video_info["channel"],
            channel_id=video_info["channel_id"],
            duration=video_info["duration"],
            thumbnail_url=video_info.get("thumbnail_url"),
            description=video_info.get("description"),
            tags=json.dumps(video_info.get("tags", [])),
            published_at=video_info.get("published_at"),
        )
        
        db.add(video)
        await db.commit()
        await db.refresh(video)
        
        return VideoResponse.model_validate(video)
    
    async def get_videos(
        self, 
        db: AsyncSession, 
        page: int = 1,
        size: int = 20,
        channel: Optional[str] = None,
        search: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> VideoListResponse:
        """Get paginated list of videos with optional filtering."""
        query = select(Video)
        
        # Apply filters
        filters = []
        if channel:
            filters.append(Video.channel.ilike(f"%{channel}%"))
        
        if search:
            filters.append(
                or_(
                    Video.title.ilike(f"%{search}%"),
                    Video.description.ilike(f"%{search}%"),
                    Video.channel.ilike(f"%{search}%")
                )
            )
        
        if tags:
            # Filter by tags (stored as JSON)
            for tag in tags:
                filters.append(Video.tags.ilike(f"%{tag}%"))
        
        if filters:
            query = query.where(*filters)
        
        # Order by created_at desc by default
        query = query.order_by(Video.created_at.desc())
        
        # Paginate
        paginator = Paginator(page=page, limit=size)
        items, total = await paginator.paginate(db, query)
        
        # Convert to response format
        video_responses = [VideoResponse.model_validate(item) for item in items]
        
        # Calculate pages
        pages = (total + size - 1) // size if size > 0 else 0
        
        return VideoListResponse(
            items=video_responses,
            total=total,
            page=page,
            size=size,
            pages=pages
        )
    
    async def get_video(self, db: AsyncSession, video_id: int) -> VideoResponse:
        """Get a single video by ID."""
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise ValueError(f"Video with ID {video_id} not found")
        
        return VideoResponse.model_validate(video)
    
    async def update_video(self, db: AsyncSession, video_id: int, update_data: VideoUpdate) -> VideoResponse:
        """Update video metadata."""
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise ValueError(f"Video with ID {video_id} not found")
        
        # Update fields
        update_dict = update_data.model_dump(exclude_unset=True)
        
        # Handle tags serialization
        if "tags" in update_dict and update_dict["tags"] is not None:
            update_dict["tags"] = json.dumps(update_dict["tags"])
        
        for field, value in update_dict.items():
            setattr(video, field, value)
        
        await db.commit()
        await db.refresh(video)
        
        return VideoResponse.model_validate(video)
    
    async def update_progress(self, db: AsyncSession, video_id: int, progress_data: VideoProgressUpdate) -> VideoResponse:
        """Update video watch progress."""
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise ValueError(f"Video with ID {video_id} not found")
        
        # Update progress
        video.last_position = progress_data.last_position
        
        # Calculate completion percentage
        if video.duration > 0:
            video.completion_percentage = min((progress_data.last_position / video.duration) * 100, 100.0)
        else:
            video.completion_percentage = 0.0
        
        await db.commit()
        await db.refresh(video)
        
        return VideoResponse.model_validate(video)
    
    async def delete_video(self, db: AsyncSession, video_id: int) -> None:
        """Delete a video."""
        result = await db.execute(select(Video).where(Video.id == video_id))
        video = result.scalar_one_or_none()
        
        if not video:
            raise ValueError(f"Video with ID {video_id} not found")
        
        await db.delete(video)
        await db.commit()
    
    async def _fetch_video_info(self, url: str) -> Dict[str, Any]:
        """Fetch video information using yt-dlp."""
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError("Could not extract video information")
                
                # Extract relevant fields
                return {
                    "youtube_id": info.get("id", ""),
                    "url": url,
                    "title": info.get("title", "Unknown Title"),
                    "channel": info.get("uploader", "Unknown Channel"),
                    "channel_id": info.get("uploader_id", ""),
                    "duration": int(info.get("duration", 0)),
                    "thumbnail_url": info.get("thumbnail"),
                    "description": info.get("description"),
                    "tags": info.get("tags", []),
                    "published_at": info.get("upload_date"),  # May need date parsing
                }
        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
            raise ValueError(f"Failed to fetch video information: {str(e)}")


# Service instance
video_service = VideoService()