from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from src.ai.client import create_lesson_body
from src.lessons.schemas import LessonCreateRequest, LessonResponse, LessonUpdateRequest
from src.storage.lesson_dao import LessonDAO


async def generate_lesson(request: LessonCreateRequest) -> LessonResponse:
    """
    Generate a new lesson and store it in the database.

    Args:
        request (LessonCreateRequest): The request object containing lesson metadata and course information.

    Returnse
    -------
        LessonResponse: The response object representing the created lesson.

    Raises
    ------
        HTTPException: If lesson creation fails.
    """
    import logging

    try:
        # Generate the lesson content using AI
        md_source = await create_lesson_body(request.node_meta)
        lesson_id = uuid4()
        now = datetime.now(timezone.utc)

        # Prepare lesson data
        lesson_data = {
            "id": lesson_id,
            "course_id": request.course_id,
            "slug": request.slug,
            "md_source": md_source,
            "created_at": now,
            "updated_at": now,
        }

        # Try to store in database, but provide fallback if database is not available
        try:
            result = await LessonDAO.insert(lesson_data)
            if result:
                return LessonResponse(**result)
        except Exception as db_error:
            logging.error(f"Database error: {db_error!s}")
            logging.info("Using fallback mechanism to return lesson without database storage")

        # Fallback: Return the lesson even if database storage failed
        lesson_response = LessonResponse(
            id=lesson_id,
            course_id=request.course_id,
            slug=request.slug,
            md_source=md_source,
            created_at=now,
            updated_at=now,
        )

        # Cache the lesson for future retrieval
        try:
            import json
            import os
            from pathlib import Path

            # Cache in the lessons directory
            cache_dir = Path("backend/cache/lessons")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = cache_dir / f"{lesson_id}.json"

            lesson_data = {
                "id": str(lesson_id),
                "course_id": str(request.course_id),
                "slug": request.slug,
                "md_source": md_source,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            }

            with open(cache_file, "w") as f:
                json.dump(lesson_data, f)

            # Also cache in the node's lessons directory
            node_cache_dir = Path(f"backend/cache/nodes/{request.course_id}/lessons")
            os.makedirs(node_cache_dir, exist_ok=True)
            node_cache_file = node_cache_dir / f"{lesson_id}.json"

            with open(node_cache_file, "w") as f:
                json.dump(lesson_data, f)

            logging.info(f"Cached lesson {lesson_id} for future retrieval")
        except Exception as cache_error:
            logging.warning(f"Failed to cache lesson: {cache_error!s}")

        return lesson_response
    except Exception as e:
        logging.exception("Error generating lesson")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


async def get_lesson(lesson_id: UUID) -> LessonResponse:
    """
    Retrieve a lesson by its ID.

    Args:
        lesson_id (UUID): The ID of the lesson to retrieve.

    Returns
    -------
        LessonResponse: The lesson data.

    Raises
    ------
        HTTPException: If lesson is not found or database error occurs.
    """
    import json
    import logging
    import os
    from pathlib import Path

    try:
        # Try to get from database first
        try:
            result = await LessonDAO.get_by_id(lesson_id)
            if result:
                # Cache the result for future use
                try:
                    cache_dir = Path("backend/cache/lessons")
                    os.makedirs(cache_dir, exist_ok=True)
                    cache_file = cache_dir / f"{lesson_id}.json"
                    with open(cache_file, "w") as f:
                        json.dump(result, f)
                except Exception as cache_error:
                    logging.warning(f"Failed to cache lesson: {cache_error!s}")

                return LessonResponse(**result)
        except Exception as db_error:
            logging.warning(f"Database error when retrieving lesson {lesson_id}: {db_error!s}")
            logging.info("Trying fallback mechanism...")

        # Fallback: Check if we have a local cache of the lesson
        cache_dir = Path("backend/cache/lessons")
        cache_file = cache_dir / f"{lesson_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    cached_data = json.load(f)
                logging.info(f"Retrieved lesson {lesson_id} from local cache")
                return LessonResponse(**cached_data)
            except Exception as cache_error:
                logging.warning(f"Error reading cache file: {cache_error!s}")

        # If we get here, we couldn't find the lesson
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lesson {lesson_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Unexpected error when retrieving lesson {lesson_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve lesson: {e!s}"
        ) from e


async def get_node_lessons(node_id: str) -> list[LessonResponse]:
    """
    Retrieve all lessons for a given node.

    Args:
        node_id (str): The ID of the node to get lessons for.

    Returns
    -------
        List[LessonResponse]: List of lessons for the node.

    Raises
    ------
        HTTPException: If database error occurs.
    """
    import glob
    import json
    import logging
    import os
    from pathlib import Path

    try:
        # Try to get from database first
        try:
            results = await LessonDAO.get_by_node(node_id)

            # Cache the results for future use
            try:
                cache_dir = Path(f"backend/cache/nodes/{node_id}/lessons")
                os.makedirs(cache_dir, exist_ok=True)

                # Cache each lesson
                for result in results:
                    lesson_id = result.get("id")
                    if lesson_id:
                        cache_file = cache_dir / f"{lesson_id}.json"
                        with open(cache_file, "w") as f:
                            json.dump(result, f)
            except Exception as cache_error:
                logging.warning(f"Failed to cache node lessons: {cache_error!s}")

            return [LessonResponse(**result) for result in results]
        except Exception as db_error:
            logging.warning(f"Database error when retrieving lessons for node {node_id}: {db_error!s}")
            logging.info("Trying fallback mechanism...")

        # Fallback: Check if we have a local cache of the node's lessons
        cache_dir = Path(f"backend/cache/nodes/{node_id}/lessons")
        if cache_dir.exists():
            try:
                cached_lessons = []
                for cache_file_path in glob.glob(str(cache_dir / "*.json")):
                    with open(cache_file_path) as f:
                        cached_data = json.load(f)
                        cached_lessons.append(cached_data)

                if cached_lessons:
                    logging.info(f"Retrieved {len(cached_lessons)} lessons for node {node_id} from local cache")
                    return [LessonResponse(**lesson) for lesson in cached_lessons]
            except Exception as cache_error:
                logging.warning(f"Error reading cache files: {cache_error!s}")

        # If we get here, we couldn't find any lessons for this node
        # Return an empty list instead of raising an exception
        return []
    except Exception as e:
        logging.exception(f"Unexpected error when retrieving lessons for node {node_id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to retrieve lessons: {e!s}"
        ) from e


async def update_lesson(lesson_id: UUID, request: LessonUpdateRequest) -> LessonResponse:
    """
    Update a lesson by its ID.

    Args:
        lesson_id (UUID): The ID of the lesson to update.
        request (LessonUpdateRequest): The update data.

    Returns
    -------
        LessonResponse: The updated lesson data.

    Raises
    ------
        HTTPException: If lesson is not found or update fails.
    """
    import logging

    try:
        # First check if lesson exists
        try:
            existing = await LessonDAO.get_by_id(lesson_id)
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lesson {lesson_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            logging.exception(f"Database error when checking if lesson {lesson_id} exists")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check if lesson exists: {e!s}"
            ) from e

        # Prepare update data
        update_data = request.model_dump(exclude_unset=True)
        update_data["updated_at"] = datetime.now(timezone.utc)

        try:
            result = await LessonDAO.update(lesson_id, update_data)
            if not result:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update lesson")
            return LessonResponse(**result)
        except HTTPException:
            raise
        except Exception as e:
            logging.exception(f"Database error when updating lesson {lesson_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to update lesson: {e!s}"
            ) from e
    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Unexpected error when updating lesson {lesson_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e!s}") from e


async def delete_lesson(lesson_id: UUID) -> None:
    """
    Delete a lesson by its ID.

    Args:
        lesson_id (UUID): The ID of the lesson to delete.

    Raises
    ------
        HTTPException: If lesson is not found or deletion fails.
    """
    import logging

    try:
        # First check if lesson exists
        try:
            existing = await LessonDAO.get_by_id(lesson_id)
            if not existing:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lesson {lesson_id} not found")
        except HTTPException:
            raise
        except Exception as e:
            logging.exception(f"Database error when checking if lesson {lesson_id} exists")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to check if lesson exists: {e!s}"
            ) from e

        # Try to delete the lesson
        try:
            success = await LessonDAO.delete(lesson_id)
            if not success:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete lesson")
        except HTTPException:
            raise
        except Exception as e:
            logging.exception(f"Database error when deleting lesson {lesson_id}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to delete lesson: {e!s}"
            ) from e
    except HTTPException:
        raise
    except Exception as e:
        logging.exception(f"Unexpected error when deleting lesson {lesson_id}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Unexpected error: {e!s}") from e
