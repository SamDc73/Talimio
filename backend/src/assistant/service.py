import json
import logging
import re
from uuid import uuid4

from fastapi import HTTPException, status

from src.ai.client import ModelManager
from src.ai.memory import get_memory_wrapper
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT

from .schemas import ChatRequest, ChatResponse, Citation


async def get_available_models():
    """Get available AI models for the assistant."""
    try:
        # Get available models from ModelManager
        memory_wrapper = get_memory_wrapper()
        model_manager = ModelManager(memory_wrapper=memory_wrapper)
        
        # For now, return a hardcoded list of common models
        # This could be enhanced to dynamically fetch from LiteLLM
        models = [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "provider": "OpenAI",
                "description": "Most capable GPT-4 model with multimodal capabilities"
            },
            {
                "id": "openai/gpt-4o-mini", 
                "name": "GPT-4o Mini",
                "provider": "OpenAI",
                "description": "Faster and more cost-effective version of GPT-4o"
            },
            {
                "id": "anthropic/claude-3-5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "provider": "Anthropic", 
                "description": "Anthropic's most balanced model for complex tasks"
            },
            {
                "id": "anthropic/claude-sonnet-4",
                "name": "Claude Sonnet 4",
                "provider": "Anthropic",
                "description": "Latest Claude model with enhanced capabilities"
            }
        ]
        
        return {"models": models}
    except Exception as e:
        logging.exception("Failed to get available models")
        # Return a fallback list
        return {
            "models": [
                {
                    "id": "openai/gpt-4o-mini",
                    "name": "GPT-4o Mini", 
                    "provider": "OpenAI",
                    "description": "Default model"
                }
            ]
        }


def detect_course_generation_intent(message: str) -> bool:
    """Detect if the user wants to generate a course."""
    course_keywords = [
        "generate a course", "create a course", "make a course", "build a course",
        "course for", "roadmap for", "learning path", "curriculum",
        "generate roadmap", "create roadmap", "make roadmap", "build roadmap"
    ]

    message_lower = message.lower()
    return any(keyword in message_lower for keyword in course_keywords)


async def trigger_course_generation(message: str, user_id: str | None = None) -> dict:
    """Extract course topic from message and trigger course generation."""
    try:
        from src.courses.schemas import CourseCreate
        from src.courses.services.course_service import CourseService
        from src.database.session import async_session_maker

        # Extract topic from message
        course_topic = re.sub(r"(?:generate|create|make|build|course|roadmap|for|me|a|an|the)\s*", "", message.lower()).strip()
        if not course_topic:
            course_topic = "General Programming Course"

        # Create course request
        course_request = CourseCreate(prompt=course_topic)

        async with async_session_maker() as session:
            course_service = CourseService(session, user_id)
            course = await course_service.create_course(course_request, user_id)

            return {
                "action": "course_generated",
                "course_id": str(course.id),
                "course_title": course.title,
                "message": f"I've created a course titled '{course.title}' for you! You can access it from your courses list."
            }

    except Exception as e:
        logging.exception("Failed to generate course")
        return {
            "action": "course_generation_failed",
            "message": f"I tried to generate a course for you, but encountered an error: {e!s}. Let me help you with your question instead."
        }


async def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """
    Chat with the AI assistant with memory integration and RAG context.

    Args:
        request: Chat request containing message, conversation history, optional user_id, and optional roadmap_id

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

        # Get RAG context and citations if roadmap_id is provided
        rag_context = ""
        citations = []
        if request.roadmap_id:
            try:
                from uuid import UUID

                from src.ai.rag.service import RAGService
                from src.database.session import async_session_maker

                rag_service = RAGService()

                async with async_session_maker() as session:
                    # Get search results with full metadata
                    search_results = await rag_service.search_documents(
                        session=session,
                        roadmap_id=UUID(request.roadmap_id),
                        query=request.message,
                        top_k=3
                    )

                    if search_results:
                        # Build context from search results
                        context_parts = [
                            f"[Source: {result.document_title}]\n{result.chunk_content}\n"
                            for result in search_results
                        ]

                        # Add citations
                        for result in search_results:
                            citations.append(Citation(
                                document_id=result.document_id,
                                document_title=result.document_title,
                                similarity_score=result.similarity_score
                            ))

                        rag_context = "\n\nRelevant roadmap materials:\n" + "\n".join(context_parts)
                        logging.info(f"Added RAG context for chat from roadmap {request.roadmap_id} with {len(citations)} citations")

            except Exception as e:
                logging.warning(f"Failed to get RAG context for chat: {e}")
                # Continue without RAG context

        # Build conversation messages
        messages = []

        # Enhanced system prompt with RAG context
        system_content = ASSISTANT_CHAT_SYSTEM_PROMPT
        if rag_context:
            system_content += "\n\nYou have access to relevant course materials. Use them to provide more specific and accurate answers. When referencing materials, cite the source documents appropriately."

        messages.append(
            {
                "role": "system",
                "content": system_content,
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

        # Add current message with RAG context
        user_message = request.message
        if rag_context:
            user_message += rag_context

        messages.append(
            {
                "role": "user",
                "content": user_message,
            },
        )

        # Check if user wants to generate a course
        if detect_course_generation_intent(request.message):
            course_result = await trigger_course_generation(request.message, request.user_id)
            response = course_result["message"]

            # Add course generation info to citations for frontend
            if course_result["action"] == "course_generated":
                citations.append(Citation(
                    document_id=0,  # Special ID for course generation
                    document_title=f"Generated Course: {course_result['course_title']}",
                    similarity_score=1.0
                ))
        else:
            # Get response from AI with memory integration
            response = await model_manager.get_completion_with_memory(messages, user_id=request.user_id, format_json=False)

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
                    metadata={"interaction_type": "chat", "conversation_id": str(uuid4()), "timestamp": "now"},
                )
            except Exception as e:
                logging.warning(f"Failed to store chat memory for user {request.user_id}: {e}")
                # Continue without failing the chat

        return ChatResponse(
            response=response,
            conversation_id=uuid4(),
            citations=citations,
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in chat with assistant")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {e!s}",
        ) from e


async def chat_with_assistant_streaming(request: ChatRequest):
    """
    Stream chat responses from the AI assistant with memory integration and RAG context.

    Args:
        request: Chat request containing message, conversation history, optional user_id, and optional roadmap_id

    Yields
    ------
        Server-sent event formatted messages containing response chunks
    """
    try:
        memory_wrapper = get_memory_wrapper()
        model_manager = ModelManager(memory_wrapper=memory_wrapper)

        # Check if user wants to generate a course first
        if detect_course_generation_intent(request.message):
            course_result = await trigger_course_generation(request.message, request.user_id)
            # Send the course generation response as a single chunk
            yield f"data: {json.dumps({'content': course_result['message'], 'done': True})}\n\n"
            return

        # Get RAG context and citations if roadmap_id is provided
        rag_context = ""
        if request.roadmap_id:
            try:
                from uuid import UUID

                from src.ai.rag.service import RAGService
                from src.database.session import async_session_maker

                rag_service = RAGService()

                async with async_session_maker() as session:
                    # Get search results with full metadata
                    search_results = await rag_service.search_documents(
                        session=session,
                        roadmap_id=UUID(request.roadmap_id),
                        query=request.message,
                        top_k=3
                    )

                    if search_results:
                        # Build context from search results
                        context_parts = [
                            f"[Source: {result.document_title}]\n{result.chunk_content}\n"
                            for result in search_results
                        ]

                        rag_context = "\n\nRelevant roadmap materials:\n" + "\n".join(context_parts)
                        logging.info(f"Added RAG context for streaming chat from roadmap {request.roadmap_id}")

            except Exception as e:
                logging.warning(f"Failed to get RAG context for streaming chat: {e}")
                # Continue without RAG context

        # Build conversation messages
        messages = []

        # Enhanced system prompt with RAG context
        system_content = ASSISTANT_CHAT_SYSTEM_PROMPT
        if rag_context:
            system_content += "\n\nYou have access to relevant course materials. Use them to provide more specific and accurate answers. When referencing materials, cite the source documents appropriately."

        messages.append(
            {
                "role": "system",
                "content": system_content,
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

        # Add current message with RAG context
        user_message = request.message
        if rag_context:
            user_message += rag_context

        messages.append(
            {
                "role": "user",
                "content": user_message,
            },
        )

        # Stream response from AI with memory integration
        full_response = ""
        async for chunk in model_manager.get_streaming_completion_with_memory(
            messages, user_id=request.user_id
        ):
            full_response += chunk
            # Send chunk in Server-Sent Events format
            yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

        # Send final message indicating completion
        yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

        # Store the conversation in memory for future context
        if request.user_id and full_response:
            try:
                await memory_wrapper.add_memory(
                    user_id=request.user_id,
                    content=f"User: {request.message}\nAssistant: {full_response}",
                    metadata={"interaction_type": "streaming_chat", "conversation_id": str(uuid4()), "timestamp": "now"},
                )
            except Exception as e:
                logging.warning(f"Failed to store streaming chat memory for user {request.user_id}: {e}")
                # Continue without failing the chat

    except Exception as e:
        logging.exception("Error in streaming chat with assistant")
        error_msg = f"Streaming chat failed: {e!s}"
        yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"
