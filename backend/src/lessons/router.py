from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from .schemas import LessonCreateRequest, LessonResponse, LessonUpdateRequest
from .service import (
    generate_lesson,
    get_lesson,
    get_node_lessons,
    update_lesson,
)


router = APIRouter(prefix="/api/v1", tags=["lessons"])


@router.post("/nodes/{node_id}/lessons", status_code=status.HTTP_201_CREATED)
async def create_lesson_endpoint(node_id: str) -> LessonResponse:
    """Generate a new lesson for a given node in the roadmap."""
    import logging

    from sqlalchemy import select

    from src.database.session import async_session_maker
    from src.roadmaps.models import Node

    try:
        node_uuid = UUID(node_id)

        # Default metadata if we can't get node info
        node_meta = {
            "title": "Learning Topic",
            "description": "A comprehensive lesson on this topic",
            "skill_level": "beginner",
        }

        # Try to fetch node information from the database
        try:
            async with async_session_maker() as session:
                # Query the node
                query = select(Node).where(Node.id == node_uuid)
                result = await session.execute(query)
                node = result.scalar_one_or_none()

                if node:
                    # Use actual node data if available
                    node_meta = {
                        "title": node.title,
                        "description": node.description,
                        "skill_level": "beginner",  # Default if not available from node
                        "content": node.content or "",  # Additional context for the lesson
                    }

                    # Try to get skill level from the roadmap
                    if hasattr(node, "roadmap") and node.roadmap:
                        node_meta["skill_level"] = node.roadmap.skill_level

                    logging.info(f"Found node in database: {node.title}")
                else:
                    logging.warning(f"Node {node_id} not found in database, using default metadata")
        except Exception as db_error:
            logging.warning(f"Error fetching node data: {db_error}. Using default metadata.")

        # Create the lesson request
        request = LessonCreateRequest(
            course_id=node_uuid,
            slug=f"lesson-{node_id}",
            node_meta=node_meta,
        )

        logging.info(f"Generating lesson for node {node_id} with metadata: {request.node_meta}")
        return await generate_lesson(request)
    except ValueError as e:
        # Handle invalid UUID
        raise HTTPException(status_code=400, detail=f"Invalid node ID format: {e!s}") from e
    except Exception as e:
        logging.exception(f"Error generating lesson for node {node_id}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/nodes/{node_id}/lessons")
async def list_node_lessons_endpoint(node_id: str) -> list[LessonResponse]:
    """List all lessons for a given node."""
    return await get_node_lessons(node_id)


@router.get("/lessons/{lesson_id}")
async def get_lesson_endpoint(lesson_id: UUID) -> LessonResponse:
    """Retrieve a specific lesson."""
    return await get_lesson(lesson_id)


@router.patch("/lessons/{lesson_id}")
async def update_lesson_endpoint(lesson_id: UUID, request: LessonUpdateRequest) -> LessonResponse:
    """Update a specific lesson."""
    return await update_lesson(lesson_id, request)
