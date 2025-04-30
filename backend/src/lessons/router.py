from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .schemas import LessonCreateRequest, LessonResponse, LessonUpdateRequest
from .service import (
    delete_lesson,
    generate_lesson,
    get_lesson,
    get_node_lessons,
    update_lesson,
)


router = APIRouter(prefix="/api/v1", tags=["lessons"])


@router.post("/nodes/{node_id}/lessons", response_model=LessonResponse, status_code=status.HTTP_201_CREATED)
async def create_lesson_endpoint(node_id: str) -> LessonResponse:
    """Generate a new lesson for a given node in the roadmap."""
    import logging

    try:
        # Create a default request
        request = LessonCreateRequest(
            course_id=UUID(node_id),
            slug=f"lesson-{node_id}",
            node_meta={
                "title": "Learning Topic",
                "description": "A comprehensive lesson on this topic",
                "skill_level": "beginner",
            },
        )

        logging.info(f"Generating lesson for node {node_id} with metadata: {request.node_meta}")
        return await generate_lesson(request)
    except ValueError as e:
        # Handle invalid UUID
        raise HTTPException(status_code=400, detail=f"Invalid node ID format: {e!s}") from e
    except Exception as e:
        logging.exception(f"Error generating lesson for node {node_id}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/nodes/{node_id}/lessons", response_model=list[LessonResponse])
async def list_node_lessons_endpoint(node_id: str) -> list[LessonResponse]:
    """List all lessons for a given node."""
    return await get_node_lessons(node_id)


@router.get("/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson_endpoint(lesson_id: UUID) -> LessonResponse:
    """Retrieve a specific lesson."""
    return await get_lesson(lesson_id)


@router.patch("/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson_endpoint(lesson_id: UUID, request: LessonUpdateRequest) -> LessonResponse:
    """Update a specific lesson."""
    return await update_lesson(lesson_id, request)


@router.delete("/lessons/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_endpoint(lesson_id: UUID) -> None:
    """Delete a specific lesson."""
    await delete_lesson(lesson_id)
