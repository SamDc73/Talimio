from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RoadmapResponse(BaseModel):
    id: UUID
    title: str
    description: str
    skill_level: str
    created_at: datetime
    updated_at: datetime

class RoadmapsListResponse(BaseModel):
    items: list[RoadmapResponse]
    total: int
    page: int
    pages: int
