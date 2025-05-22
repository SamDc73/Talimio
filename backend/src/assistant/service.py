import logging
from uuid import uuid4

from fastapi import HTTPException, status

from src.ai.client import ModelManager
from src.assistant.schemas import (
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
    Chat with the AI assistant.

    Args:
        request: Chat request containing message and conversation history

    Returns
    -------
        ChatResponse: Response from the assistant

    Raises
    ------
        HTTPException: If chat fails
    """
    try:
        model_manager = ModelManager()

        # Build conversation messages
        messages = []
        messages.append({
            "role": "system",
            "content": "You are a helpful learning assistant. Provide clear, educational responses that help users learn new topics. Be encouraging and supportive.",
        })

        # Add conversation history
        for msg in request.conversation_history:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Add current message
        messages.append({
            "role": "user",
            "content": request.message,
        })

        # Get response from AI
        response = await model_manager._get_completion(messages, format_json=False)

        if not response or not isinstance(response, str):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get response from assistant",
            )

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
    Generate a complete course on a topic.

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
        model_manager = ModelManager()

        prompt = f"""
        Create a comprehensive {request.duration_weeks}-week course on "{request.topic}" for {request.skill_level} level learners.
        
        {f'Course Description: {request.description}' if request.description else ''}
        
        Generate a structured course with modules. Each module should be a weekly unit.
        
        For each module, provide:
        - Title (clear and descriptive)
        - Description (what will be covered)
        - Content (detailed learning objectives and key topics)
        - Estimated hours to complete
        
        Format as JSON:
        {{
            "title": "Complete Course Title",
            "description": "Course overview and what students will learn",
            "modules": [
                {{
                    "title": "Module 1 Title",
                    "description": "What this module covers",
                    "content": "Detailed learning objectives and topics",
                    "order": 0,
                    "estimated_hours": 5
                }}
            ]
        }}
        """

        messages = [
            {"role": "system", "content": "You are an expert curriculum designer creating structured learning courses."},
            {"role": "user", "content": prompt},
        ]

        response = await model_manager._get_completion(messages, format_json=True)

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

        return GenerateCourseResponse(
            course_id=uuid4(),
            title=course_title,
            description=course_description,
            skill_level=request.skill_level,
            modules=modules,
            total_estimated_hours=total_hours,
        )

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
    Generate flashcards from content.

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
        model_manager = ModelManager()

        topic = request.topic or "General Topic"

        prompt = f"""
        Create {request.num_cards} flashcards from the following content about {topic}:
        
        Content:
        {request.content}
        
        Generate flashcards that:
        - Focus on key concepts and important facts
        - Have clear, concise questions
        - Provide complete, accurate answers
        - Vary in difficulty (easy, medium, hard)
        - Include relevant tags for categorization
        
        Format as JSON:
        {{
            "flashcards": [
                {{
                    "question": "Clear, specific question",
                    "answer": "Complete, accurate answer",
                    "difficulty": "easy|medium|hard",
                    "tags": ["tag1", "tag2"]
                }}
            ]
        }}
        """

        messages = [
            {"role": "system", "content": "You are an expert at creating educational flashcards that help students learn and retain information effectively."},
            {"role": "user", "content": prompt},
        ]

        response = await model_manager._get_completion(messages, format_json=True)

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

        return GenerateFlashcardsResponse(
            flashcards=flashcards,
            topic=topic,
            total_cards=len(flashcards),
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error generating flashcards")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Flashcard generation failed: {e!s}",
        ) from e
