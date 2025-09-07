"""Enhanced assistant service with context-aware RAG integration."""

import json
import logging
import re
from collections.abc import AsyncGenerator
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import text as sql_text

from src.ai.ai_service import get_ai_service
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT, RAG_ASSISTANT_PROMPT
from src.ai.rag.schemas import SearchResult
from src.courses.facade import CoursesFacade
from src.courses.schemas import CourseCreate
from src.database.session import async_session_maker

from .context import ContextData, ContextManager
from .schemas import ChatRequest, Citation, CitationMatch


logger = logging.getLogger(__name__)


class CourseGenerationError(Exception):
    """Raised when course generation fails."""



async def get_available_models() -> dict:
    """Get available AI models for the assistant."""
    try:
        # For now, return a hardcoded list of common models
        # This could be enhanced to dynamically fetch from LiteLLM
        models = [
            {
                "id": "openai/gpt-4o",
                "name": "GPT-4o",
                "provider": "OpenAI",
                "description": "Most capable GPT-4 model with multimodal capabilities",
            },
            {
                "id": "openai/gpt-4o-mini",
                "name": "GPT-4o Mini",
                "provider": "OpenAI",
                "description": "Faster and more cost-effective version of GPT-4o",
            },
            {
                "id": "anthropic/claude-3-5-sonnet",
                "name": "Claude 3.5 Sonnet",
                "provider": "Anthropic",
                "description": "Anthropic's most balanced model for complex tasks",
            },
            {
                "id": "anthropic/claude-sonnet-4",
                "name": "Claude Sonnet 4",
                "provider": "Anthropic",
                "description": "Latest Claude model with enhanced capabilities",
            },
        ]

        return {"models": models}
    except Exception:
        logging.exception("Failed to get available models")
        # Return a fallback list
        return {
            "models": [
                {
                    "id": "openai/gpt-4o-mini",
                    "name": "GPT-4o Mini",
                    "provider": "OpenAI",
                    "description": "Default model",
                },
            ],
        }


def detect_course_generation_intent(message: str) -> bool:
    """Detect if the user wants to generate a course."""
    course_keywords = [
        "generate a course",
        "create a course",
        "make a course",
        "build a course",
        "course for",
        "roadmap for",
        "learning path",
        "curriculum",
        "generate roadmap",
        "create roadmap",
        "make roadmap",
        "build roadmap",
    ]

    message_lower = message.lower()
    return any(keyword in message_lower for keyword in course_keywords)


async def trigger_course_generation(message: str, user_id: UUID | None = None) -> dict:
    """Extract course topic from message and trigger course generation."""
    try:
        # Extract topic from message
        course_topic = re.sub(
            r"(?:generate|create|make|build|course|roadmap|for|me|a|an|the)\s*",
            "",
            message.lower(),
        ).strip()
        if not course_topic:
            course_topic = "General Programming Course"

        # Create course request
        course_request = CourseCreate(prompt=course_topic)

        async with async_session_maker():
            # user_id is now required - no auth checks in services
            if user_id is None:
                msg = "user_id is required for course generation"
                raise ValueError(msg)

            course_service = CoursesFacade()
            result = await course_service.create_course(course_request.model_dump(), user_id)

            if not result.get("success"):
                raise CourseGenerationError(result.get("error", "Failed to create course"))

            course = result["course"]

            return {
                "action": "course_generated",
                "course_id": str(course.id),
                "course_title": course.title,
                "message": f"I've created a course titled '{course.title}' for you! You can access it from your courses list.",
            }

    except Exception as e:
        logging.exception("Failed to generate course")
        return {
            "action": "course_generation_failed",
            "message": f"I tried to generate a course for you, but encountered an error: {e!s}. Let me help you with your question instead.",
        }


class AssistantService:
    """Assistant service with streaming support and context-aware RAG integration."""

    def __init__(self) -> None:
        self.context_manager = ContextManager()
        self._ai_service = get_ai_service()

    async def _get_immediate_context(self, request: ChatRequest) -> ContextData | None:
        """Get immediate context from current page/timestamp."""
        if not (request.context_type and request.context_id):
            return None

        try:
            # Ensure user_id is included in context_meta for course context
            context_meta = request.context_meta or {}
            if request.user_id:
                context_meta["user_id"] = request.user_id

            context_data = await self.context_manager.get_context(
                context_type=request.context_type,
                resource_id=request.context_id,
                context_meta=context_meta,
            )

            if context_data:
                logger.info("Retrieved immediate context: %s", context_data.source)

            return context_data

        except Exception as e:
            logger.warning("Failed to get immediate context: %s", e)
            return None

    async def _get_semantic_context(self, request: ChatRequest) -> list[SearchResult]:
        """Get semantic context from the RAG system using VectorRAG."""
        logger.info("Getting semantic context for request: %s", request)

        # Only use VectorRAG for course context
        if request.context_type == "course" and request.context_id:
            try:
                results = await self._try_contextual_search(request)
                if results:
                    logger.info("VectorRAG search succeeded with %d results", len(results))
                    return results
            except Exception as e:
                logger.warning("VectorRAG search failed: %s", e)

        return []

    async def _try_contextual_search(self, request: ChatRequest) -> list[SearchResult]:
        """Try contextual search if context is available."""
        if not (request.context_type and request.context_id):
            return []  # Skip if no context available

        # Use VectorRAG for course context (with embeddings!)
        if request.context_type == "course":
            try:
                from uuid import UUID

                from src.ai.rag.embeddings import VectorRAG
                from src.database.session import async_session_maker

                vector_rag = VectorRAG()
                async with async_session_maker() as session:
                    # Convert context_id to UUID if it's a string
                    course_id = request.context_id if isinstance(request.context_id, UUID) else UUID(str(request.context_id))
                    results = await vector_rag.search_course_documents_vector(
                        session=session,
                        course_id=course_id,
                        query=request.message,
                        limit=5
                    )
                    logger.info("Retrieved %d chunks using VectorRAG for course", len(results))
                    return results
            except Exception:
                logger.exception("VectorRAG search failed")
                return []  # Return empty results on failure

        # Book and video context search can be added when their RAG pipelines are ready
        logger.info("Context type %s not yet supported for RAG search", request.context_type)
        return []



    async def _build_enhanced_messages(
        self,
        request: ChatRequest,
        immediate_context: ContextData | None,
        semantic_context: list[SearchResult],
    ) -> list[dict]:
        """Build enhanced message list with all context types."""
        messages = []

        # RAG-specific system prompt
        if semantic_context:
            system_content = RAG_ASSISTANT_PROMPT
        else:
            system_content = ASSISTANT_CHAT_SYSTEM_PROMPT

            # Add context descriptions to system prompt
            if immediate_context:
                system_content += f"\n\nYou have access to the user's current context in the {request.context_type}. Use this context to provide relevant assistance related to what they're currently viewing."

        messages.append({"role": "system", "content": system_content})

        # Add conversation history
        messages.extend({"role": msg.role, "content": msg.content} for msg in request.conversation_history)

        # Build enhanced user message
        user_message = request.message

        # Add immediate context
        if immediate_context:
            user_message += f"\n\nCurrent {request.context_type} context from {immediate_context.source}:\n{immediate_context.content}"

        # Add semantic context
        if semantic_context:
            semantic_parts = []
            for i, result in enumerate(semantic_context[:3]):  # Limit to top 3
                # Use content property
                content = result.content
                semantic_parts.append(
                    f"[Relevant content {i + 1} - Score: {result.similarity_score:.2f}]\n{content}",
                )
            user_message += "\n\nSemantically related content:\n" + "\n\n".join(semantic_parts)

        messages.append({"role": "user", "content": user_message})
        return messages

    async def _generate_response(  # noqa: C901 - Complex due to multiple response scenarios
        self, request: ChatRequest, messages: list[dict], immediate_context: ContextData | None
    ) -> str:
        """Generate AI response with course generation detection and enhanced context."""
        # Check for course generation intent
        if detect_course_generation_intent(request.message):
            course_result = await trigger_course_generation(request.message, request.user_id)
            return course_result["message"]

        try:
            # Build context metadata for AI service
            context_meta = request.context_meta or {}
            if immediate_context:
                # Add context-specific metadata
                if request.context_type == "book" and "page" in context_meta:
                    context_meta["chapter"] = immediate_context.metadata.get("chapter")
                elif request.context_type == "video" and "timestamp" in context_meta:
                    context_meta["title"] = immediate_context.metadata.get("title")

            # Get standard AI response using AIService with rich context
            response = await self._ai_service.process_content(
                content_type="assistant",
                action="chat",
                user_id=request.user_id,
                message=request.message,
                context={
                    "messages": messages,
                    "context_type": request.context_type,
                    "context_id": request.context_id,
                    "context_meta": context_meta,
                    "interaction_type": "assistant_chat",
                },
                history=messages[1:] if len(messages) > 1 else None,  # Skip system message
            )

            if not response or not isinstance(response, str):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to get response from assistant",
                )

            return response

        except Exception:
            # Log the error but don't fail completely
            logger.exception("AI model error")

            # Extract context from messages to provide a useful fallback
            context_info = []
            for msg in messages:
                if msg["role"] == "user" and "Semantically related content:" in msg["content"]:
                    # Extract the semantic content
                    parts = msg["content"].split("Semantically related content:")
                    if len(parts) > 1:
                        context_info.append(parts[1].strip())

            if context_info:
                fallback_response = (
                    "I found relevant information from your documents, but I'm currently unable to generate a complete response "
                    "due to a temporary AI service issue. Here's the relevant content I found:\n\n"
                    + "\n".join(context_info)
                )
            else:
                fallback_response = (
                    "I'm experiencing a temporary issue connecting to the AI service. "
                    "Please try again in a moment, or check your AI model configuration."
                )

            return fallback_response

    def _collect_citations(
        self,
        semantic_context: list[SearchResult],
        _request: ChatRequest,
    ) -> list[Citation]:
        """Collect citations from all context sources."""
        citations = []

        # Add semantic context citations
        citations.extend(
            [
                Citation(
                    document_id=result.chunk_id,
                    document_title=result.metadata.get("title", "Document"),
                    similarity_score=result.similarity_score,
                )
                for result in semantic_context
            ],
        )

        return citations

    async def find_book_citations(
        self,
        book_id: UUID,
        _response_text: str,
        _similarity_threshold: float = 0.75,
    ) -> list[CitationMatch]:
        """Find text locations in a book for citation highlighting.

        Args:
            book_id: UUID of the book
            _response_text: Text to find citations for (not yet implemented)
            _similarity_threshold: Minimum similarity score for matches (not yet implemented)

        Returns
        -------
            List of citation matches with page numbers and coordinates
        """
        # Validate book exists and has been processed
        async with async_session_maker() as session:
            result = await session.execute(
                sql_text("""
                    SELECT rag_status
                    FROM books
                    WHERE id = :book_id
                """),
                {"book_id": str(book_id)},
            )
            book = result.fetchone()

            if not book:
                msg = f"Book not found: {book_id}"
                raise ValueError(msg)

            if book.rag_status != "completed":
                msg = f"Book has not been processed for RAG. Current status: {book.rag_status}"
                raise ValueError(msg)

        # Citation highlighting feature pending implementation
        return []


    async def chat_with_assistant(self, request: ChatRequest) -> AsyncGenerator[str, None]:  # noqa: C901
        """Enhanced streaming chat with context-aware RAG integration."""
        try:
            # Check if user wants to generate a course first
            if detect_course_generation_intent(request.message):
                course_result = await trigger_course_generation(request.message, request.user_id)
                # Send the course generation response as a single chunk
                yield f"data: {json.dumps({'content': course_result['message'], 'done': True})}\n\n"
                return

            # Get all context types (same as non-streaming)
            immediate_context = await self._get_immediate_context(request)
            semantic_context = await self._get_semantic_context(request)

            # Build enhanced messages
            messages = await self._build_enhanced_messages(
                request,
                immediate_context,
                semantic_context,
            )

            # Since AIService doesn't support streaming yet, we'll get the full response
            # and simulate streaming by chunking it
            try:
                # Build context metadata for AI service
                context_meta = request.context_meta or {}
                if immediate_context:
                    # Add context-specific metadata
                    if request.context_type == "book" and "page" in context_meta:
                        context_meta["chapter"] = immediate_context.metadata.get("chapter")
                    elif request.context_type == "video" and "timestamp" in context_meta:
                        context_meta["title"] = immediate_context.metadata.get("title")

                response = await self._ai_service.process_content(
                    content_type="assistant",
                    action="chat",
                    user_id=request.user_id,
                    message=request.message,
                    context={
                        "messages": messages,
                        "context_type": request.context_type,
                        "context_id": request.context_id,
                        "context_meta": context_meta,
                        "interaction_type": "assistant_chat",
                    },
                    history=messages[1:] if len(messages) > 1 else None,
                )

                # Simulate streaming by chunking the response
                chunk_size = 50  # Characters per chunk
                for i in range(0, len(response), chunk_size):
                    chunk = response[i : i + chunk_size]
                    yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

                # Send final message indicating completion
                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

            except Exception:
                logger.exception("AI streaming error")

                # Provide fallback response with context
                context_info = []
                for msg in messages:
                    if msg["role"] == "user" and "Semantically related content:" in msg["content"]:
                        parts = msg["content"].split("Semantically related content:")
                        if len(parts) > 1:
                            context_info.append(parts[1].strip())

                if context_info:
                    fallback_msg = (
                        "I found relevant information from your documents, but I'm currently unable to generate a complete response "
                        "due to a temporary AI service issue. Here's the relevant content I found:\n\n"
                        + "\n".join(context_info)
                    )
                else:
                    fallback_msg = (
                        "I'm experiencing a temporary issue connecting to the AI service. "
                        "Please try again in a moment, or check your AI model configuration."
                    )

                # Send fallback as a single chunk
                yield f"data: {json.dumps({'content': fallback_msg, 'done': False})}\n\n"
                yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

            # Memory is now automatically integrated in the AI service - no manual storage needed

        except Exception as e:
            logger.exception("Error in enhanced streaming chat")
            error_msg = f"Streaming chat failed: {e!s}"
            yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"


# Service instances
# Single assistant service instance
assistant_service = AssistantService()


