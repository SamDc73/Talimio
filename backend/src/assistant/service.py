import logging
from uuid import uuid4

from fastapi import HTTPException, status

from src.ai.client import ModelManager
from src.ai.memory import get_memory_wrapper
from src.ai.prompts import (
    ASSISTANT_CHAT_SYSTEM_PROMPT,
    COURSE_GENERATION_PROMPT,
    FLASHCARD_GENERATION_PROMPT,
)

from .schemas import (
    ChatRequest,
    ChatResponse,
    CourseModule,
    FlashcardItem,
    GenerateCourseRequest,
    GenerateCourseResponse,
    GenerateFlashcardsRequest,
    GenerateFlashcardsResponse,
)


async def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """
    Chat with the AI assistant with memory integration.

    Args:
        request: Chat request containing message, conversation history, and optional user_id

    Returns
    -------
        ChatResponse: Response from the assistant

    Raises
    ------
        HTTPException: If chat fails
    """
    try:
        memory_wrapper = get_memory_wrapper()
        model_manager = ModelManager(memory_wrapper=memory_wrapper)

        # Build conversation messages
        messages = []
        messages.append(
            {
                "role": "system",
                "content": ASSISTANT_CHAT_SYSTEM_PROMPT,
            },
        )

        # Add conversation history
        messages.extend(
            {
                "role": msg.role,
                "content": msg.content,
            }
            for msg in request.conversation_history
        )

        # Add current message
        messages.append(
            {
                "role": "user",
                "content": request.message,
            },
        )

        # Get response from AI with memory integration
        response = await model_manager.get_completion_with_memory(
            messages,
            user_id=request.user_id,
            format_json=False
        )

        if not response or not isinstance(response, str):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get response from assistant",
            )

        # Store the conversation in memory for future context
        if request.user_id:
            try:
                await memory_wrapper.add_memory(
                    user_id=request.user_id,
                    content=f"User: {request.message}\nAssistant: {response}",
                    metadata={
                        "interaction_type": "chat",
                        "conversation_id": str(uuid4()),
                        "timestamp": "now"
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to store chat memory for user {request.user_id}: {e}")
                # Continue without failing the chat

        return ChatResponse(
            response=response,
            conversation_id=uuid4(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in chat with assistant")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {e!s}",
        ) from e


async def generate_course(request: GenerateCourseRequest) -> GenerateCourseResponse:
    """
    Generate a complete course on a topic with personalization.

    Args:
        request: Course generation request

    Returns
    -------
        GenerateCourseResponse: Generated course content

    Raises
    ------
        HTTPException: If course generation fails
    """
    try:
        memory_wrapper = get_memory_wrapper()
        model_manager = ModelManager(memory_wrapper=memory_wrapper)

        prompt = COURSE_GENERATION_PROMPT.format(
            topic=request.topic,
            duration=request.duration_weeks,
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert curriculum designer creating structured learning courses.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await model_manager.get_completion_with_memory(
            messages,
            user_id=request.user_id,
            format_json=True
        )

        if not isinstance(response, dict):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid response format from AI model",
            )

        # Extract and validate course data
        course_title = response.get("title", f"Complete {request.topic} Course")
        course_description = response.get("description", f"A comprehensive course on {request.topic}")
        modules_data = response.get("modules", [])

        modules = []
        total_hours = 0

        for i, module_data in enumerate(modules_data):
            estimated_hours = module_data.get("estimated_hours", 5)
            module = CourseModule(
                title=module_data.get("title", f"Module {i + 1}"),
                description=module_data.get("description", ""),
                content=module_data.get("content", ""),
                order=i,
                estimated_hours=estimated_hours,
            )
            modules.append(module)
            total_hours += estimated_hours

        course_response = GenerateCourseResponse(
            course_id=uuid4(),
            title=course_title,
            description=course_description,
            skill_level=request.skill_level,
            modules=modules,
            total_estimated_hours=total_hours,
        )

        # Track course generation in memory
        if request.user_id:
            try:
                await memory_wrapper.add_memory(
                    user_id=request.user_id,
                    content=f"Generated course '{course_title}' on {request.topic}",
                    metadata={
                        "interaction_type": "course_generation",
                        "topic": request.topic,
                        "skill_level": request.skill_level,
                        "duration_weeks": request.duration_weeks,
                        "total_hours": total_hours,
                        "num_modules": len(modules),
                        "timestamp": "now"
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to store course generation memory for user {request.user_id}: {e}")

        return course_response

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error generating course")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Course generation failed: {e!s}",
        ) from e


async def generate_flashcards(request: GenerateFlashcardsRequest) -> GenerateFlashcardsResponse:
    """
    Generate flashcards from content with personalization.

    Args:
        request: Flashcard generation request

    Returns
    -------
        GenerateFlashcardsResponse: Generated flashcards

    Raises
    ------
        HTTPException: If flashcard generation fails
    """
    try:
        memory_wrapper = get_memory_wrapper()
        model_manager = ModelManager(memory_wrapper=memory_wrapper)

        topic = request.topic or "General Topic"

        prompt = FLASHCARD_GENERATION_PROMPT.format(
            content=request.content,
            count=request.num_cards,
        )

        messages = [
            {
                "role": "system",
                "content": "You are an expert at creating educational flashcards that help students learn and retain information effectively.",
            },
            {"role": "user", "content": prompt},
        ]

        response = await model_manager.get_completion_with_memory(
            messages,
            user_id=request.user_id,
            format_json=True
        )

        if not isinstance(response, dict) or "flashcards" not in response:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid response format from AI model",
            )

        flashcards_data = response.get("flashcards", [])
        flashcards = []

        for card_data in flashcards_data:
            flashcard = FlashcardItem(
                question=card_data.get("question", ""),
                answer=card_data.get("answer", ""),
                difficulty=card_data.get("difficulty", "medium"),
                tags=card_data.get("tags", []),
            )
            flashcards.append(flashcard)

        flashcard_response = GenerateFlashcardsResponse(
            flashcards=flashcards,
            topic=topic,
            total_cards=len(flashcards),
        )

        # Track flashcard generation in memory
        if request.user_id:
            try:
                await memory_wrapper.add_memory(
                    user_id=request.user_id,
                    content=f"Generated {len(flashcards)} flashcards on {topic}",
                    metadata={
                        "interaction_type": "flashcard_generation",
                        "topic": topic,
                        "num_cards": len(flashcards),
                        "content_preview": request.content[:200],
                        "timestamp": "now"
                    }
                )
            except Exception as e:
                logging.warning(f"Failed to store flashcard generation memory for user {request.user_id}: {e}")

        return flashcard_response

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error generating flashcards")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flashcard generation failed: {e!s}",
        ) from e
