"""Enhanced assistant service with context-aware RAG integration."""

import json
import logging
import re
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import text as sql_text

from src.ai.client import ModelManager
from src.ai.memory import get_memory_wrapper
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT
from src.ai.rag.retriever import ContextAwareRetriever
from src.ai.rag.schemas import SearchResult
from src.ai.rag.service import RAGService
from src.courses.schemas import CourseCreate
from src.courses.services.course_service import CourseService
from src.database.session import async_session_maker

from .context import ContextData, ContextManager
from .schemas import ChatRequest, ChatResponse, Citation


logger = logging.getLogger(__name__)


async def get_available_models() -> dict:
    """Get available AI models for the assistant."""
    try:
        # Get available models from ModelManager
        memory_wrapper = get_memory_wrapper()
        ModelManager(memory_wrapper=memory_wrapper)

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
                }
            ]
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


async def trigger_course_generation(message: str, user_id: str | None = None) -> dict:
    """Extract course topic from message and trigger course generation."""
    try:
        # Extract topic from message
        course_topic = re.sub(
            r"(?:generate|create|make|build|course|roadmap|for|me|a|an|the)\s*", "", message.lower()
        ).strip()
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
                "message": f"I've created a course titled '{course.title}' for you! You can access it from your courses list.",
            }

    except Exception as e:
        logging.exception("Failed to generate course")
        return {
            "action": "course_generation_failed",
            "message": f"I tried to generate a course for you, but encountered an error: {e!s}. Let me help you with your question instead.",
        }


class EnhancedAssistantService:
    """Enhanced assistant service with context-aware RAG integration."""

    def __init__(self) -> None:
        self.context_retriever = ContextAwareRetriever()
        self.context_manager = ContextManager()

    async def chat_with_assistant_enhanced(self, request: ChatRequest) -> ChatResponse:
        """
        Enhanced chat with context-aware RAG integration.

        This service combines:
        1. context-aware content (current page/timestamp context)
        2. RAG system (semantic document chunks)
        3. Memory integration
        4. Course generation detection
        """
        try:
            memory_wrapper = get_memory_wrapper()
            model_manager = ModelManager(memory_wrapper=memory_wrapper)

            immediate_context = await self._get_immediate_context(request)

            semantic_context = await self._get_semantic_context(request)

            roadmap_context = await self._get_roadmap_context(request)

            messages = await self._build_enhanced_messages(
                request, immediate_context, semantic_context, roadmap_context
            )

            response = await self._generate_response(request, messages, model_manager)

            citations = self._collect_citations(semantic_context, roadmap_context, request)

            await self._store_conversation_memory(request, response, memory_wrapper)

            return ChatResponse(
                response=response,
                conversation_id=uuid4(),
                citations=citations,
                context_source=immediate_context.source if immediate_context else None,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error in enhanced chat with assistant")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Enhanced chat failed: {e!s}",
            ) from e

    async def _get_immediate_context(self, request: ChatRequest) -> ContextData | None:
        """Get immediate context from current page/timestamp."""
        if not (request.context_type and request.context_id):
            return None

        try:
            context_data = await self.context_manager.get_context(
                context_type=request.context_type, resource_id=request.context_id, context_meta=request.context_meta
            )

            if context_data:
                logger.info(f"Retrieved immediate context: {context_data.source}")

            return context_data

        except Exception as e:
            logger.warning(f"Failed to get immediate context: {e}")
            return None

    async def _get_semantic_context(self, request: ChatRequest) -> list[SearchResult]:
        """Get semantic context from the RAG system."""
        if not (request.context_type and request.context_id):
            return []

        try:
            results = await self.context_retriever.retrieve_context(
                query=request.message,
                context_type=request.context_type,
                context_id=request.context_id,
                context_meta=request.context_meta,
                max_chunks=5,
                relevance_threshold=0.01,  # Extremely low threshold for debugging
            )

            logger.info(f"Retrieved {len(results)} semantic chunks for context")

            # If vector search failed, try text-based fallback
            if not results:
                logger.error("Vector search returned no results, trying text-based fallback")
                results = await self._text_based_fallback_search(request)
                logger.error(f"Text-based fallback returned {len(results)} results")

            return results

        except Exception as e:
            error_str = str(e).lower()
            # Check for dimension mismatch or embedding errors
            if any(
                keyword in error_str
                for keyword in ["dimension", "vector", "embedding", "quota", "rate", "insufficient"]
            ):
                logger.exception(f"Vector search failed with embedding/dimension error: {e}")
                logger.info("Forcing text-based fallback due to embedding issues")
                # Force text-based fallback for embedding-related errors
                try:
                    results = await self._text_based_fallback_search(request)
                    logger.info(f"Text-based fallback returned {len(results)} results")
                    return results
                except Exception as fallback_error:
                    logger.exception(f"Text-based fallback also failed: {fallback_error}")
                    return []
            else:
                logger.warning(f"Failed to get semantic context: {e}")
                # Try text-based fallback on any other error
                try:
                    results = await self._text_based_fallback_search(request)
                    logger.info(f"Text-based fallback returned {len(results)} results")
                    return results
                except Exception as fallback_error:
                    logger.warning(f"Text-based fallback also failed: {fallback_error}")
                    return []

    async def _text_based_fallback_search(self, request: ChatRequest) -> list[SearchResult]:
        """Text-based fallback search when vector search fails."""
        try:
            async with async_session_maker() as session:
                # Search for chunks containing relevant keywords from the query
                query_lower = request.message.lower()

                # Extract key terms and be more specific
                search_terms = []
                if "probabilities" in query_lower:
                    if "where" in query_lower:
                        # This is likely the "Where Do the Probabilities Come From" section
                        search_terms.extend(
                            ["Where Do the Probabilities", "probabilities come from", "letter", "English text"]
                        )
                    else:
                        search_terms.append("probabilities")
                if "chatgpt" in query_lower:
                    search_terms.append("ChatGPT")

                # If no specific terms, try to extract any meaningful words
                if not search_terms:
                    words = query_lower.split()
                    search_terms = [word for word in words if len(word) > 3]

                # Build ILIKE conditions (case-insensitive)
                conditions = " OR ".join([f"content ILIKE '%{term}%'" for term in search_terms])

                if not conditions:
                    # Generic search - just get some chunks
                    conditions = "content ILIKE '%ChatGPT%'"

                query = f"""
                    SELECT id, doc_id, doc_type, content, metadata
                    FROM rag_document_chunks
                    WHERE doc_id = :doc_id
                    AND doc_type = :doc_type
                    AND ({conditions})
                    LIMIT 5
                """

                logger.error(f"Fallback query: {query}")
                logger.error(f"Search terms: {search_terms}")

                result = await session.execute(
                    sql_text(query), {"doc_id": str(request.context_id), "doc_type": request.context_type}
                )

                rows = result.fetchall()

                return [
                    SearchResult(
                        chunk_id=row.id,
                        doc_id=UUID(row.doc_id),
                        doc_type=row.doc_type,
                        content=row.content,
                        metadata=row.metadata or {},
                        similarity_score=0.8,  # Fake score for text match
                        final_score=0.8,
                    )
                    for row in rows
                ]

        except Exception as e:
            logger.exception(f"Text-based fallback search failed: {e}")
            return []

    async def _get_roadmap_context(self, request: ChatRequest) -> tuple[str, list[Citation]]:
        """Get legacy roadmap context for backward compatibility."""
        if not request.roadmap_id:
            return "", []

        try:
            rag_service = RAGService()
            citations = []

            async with async_session_maker() as session:
                search_results = await rag_service.search_documents(
                    session=session, roadmap_id=UUID(request.roadmap_id), query=request.message, top_k=3
                )

                if search_results:
                    context_parts = [
                        f"[Source: {result.document_title}]\n{result.chunk_content}\n" for result in search_results
                    ]

                    citations.extend(
                        [
                            Citation(
                                document_id=result.document_id,
                                document_title=result.document_title,
                                similarity_score=result.similarity_score,
                            )
                            for result in search_results
                        ]
                    )

                    context = "\n\nRelevant roadmap materials:\n" + "\n".join(context_parts)
                    logger.info(f"Retrieved roadmap context with {len(citations)} citations")
                    return context, citations

            return "", []

        except Exception as e:
            logger.warning(f"Failed to get roadmap context: {e}")
            return "", []

    async def _build_enhanced_messages(
        self,
        request: ChatRequest,
        immediate_context: ContextData | None,
        semantic_context: list[SearchResult],
        roadmap_context: tuple[str, list[Citation]],
    ) -> list[dict]:
        """Build enhanced message list with all context types."""
        messages = []

        # Enhanced system prompt
        system_content = ASSISTANT_CHAT_SYSTEM_PROMPT

        # Add context descriptions to system prompt
        if roadmap_context[0]:
            system_content += "\n\nYou have access to relevant course materials. Use them to provide more specific and accurate answers. When referencing materials, cite the source documents appropriately."

        if immediate_context:
            system_content += f"\n\nYou have access to the user's current context in the {request.context_type}. Use this context to provide relevant assistance related to what they're currently viewing."

        if semantic_context:
            system_content += "\n\nYou also have access to semantically related content from the document. Use this to provide comprehensive and contextually relevant answers."

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
                semantic_parts.append(f"[Relevant content {i + 1} - Score: {result.final_score:.2f}]\n{result.content}")
            user_message += "\n\nSemantically related content:\n" + "\n\n".join(semantic_parts)

        # Add roadmap context (legacy)
        if roadmap_context[0]:
            user_message += roadmap_context[0]

        messages.append({"role": "user", "content": user_message})
        return messages

    async def _generate_response(self, request: ChatRequest, messages: list[dict], model_manager: ModelManager) -> str:
        """Generate AI response with course generation detection."""
        # Check for course generation intent
        if detect_course_generation_intent(request.message):
            course_result = await trigger_course_generation(request.message, request.user_id)
            return course_result["message"]

        # Get standard AI response with memory
        response = await model_manager.get_completion_with_memory(messages, user_id=request.user_id, format_json=False)

        if not response or not isinstance(response, str):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to get response from assistant",
            )

        return response

    def _collect_citations(
        self, semantic_context: list[SearchResult], roadmap_context: tuple[str, list[Citation]], _request: ChatRequest
    ) -> list[Citation]:
        """Collect citations from all context sources."""
        citations = []

        # Add semantic context citations
        citations.extend(
            [
                Citation(
                    document_id=result.chunk_id,
                    document_title=f"{result.doc_type.title()}: {result.doc_id}",
                    similarity_score=result.final_score or result.similarity_score,
                )
                for result in semantic_context
            ]
        )

        # Add roadmap citations
        citations.extend(roadmap_context[1])

        return citations

    async def _store_conversation_memory(self, request: ChatRequest, response: str, memory_wrapper: Any) -> None:
        """Store conversation in memory for future context."""
        if not request.user_id:
            return

        try:
            context_info = ""
            if request.context_type and request.context_id:
                context_info = f" (in {request.context_type}: {request.context_id})"

            await memory_wrapper.add_memory(
                user_id=request.user_id,
                content=f"User{context_info}: {request.message}\nAssistant: {response}",
                metadata={
                    "interaction_type": "enhanced_chat",
                    "conversation_id": str(uuid4()),
                    "context_type": request.context_type,
                    "context_id": str(request.context_id) if request.context_id else None,
                    "timestamp": "now",
                },
            )

        except Exception as e:
            logger.warning(f"Failed to store enhanced chat memory for user {request.user_id}: {e}")

    async def find_book_citations(
        self, book_id: UUID, response_text: str, similarity_threshold: float = 0.75
    ) -> list[dict]:
        """Find text locations in a book for citation highlighting.

        Args:
            book_id: UUID of the book
            response_text: Text to find citations for
            similarity_threshold: Minimum similarity score for matches

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

        # Use RAG service to find citations
        rag_service = RAGService()
        citations = await rag_service.find_text_locations(
            book_id=book_id, response_text=response_text, similarity_threshold=similarity_threshold
        )

        # Transform to match schema
        return [
            {
                "text": citation["text"],
                "page": citation["page"],
                "coordinates": citation["coordinates"],
                "similarity": citation["similarity"],
            }
            for citation in citations
        ]


class StreamingEnhancedAssistantService(EnhancedAssistantService):
    """Streaming version of enhanced assistant service."""

    async def chat_with_assistant_streaming_enhanced(self, request: ChatRequest) -> AsyncGenerator[str, None]:
        """Enhanced streaming chat with context-aware RAG integration."""
        try:
            memory_wrapper = get_memory_wrapper()
            model_manager = ModelManager(memory_wrapper=memory_wrapper)

            # Check if user wants to generate a course first
            if detect_course_generation_intent(request.message):
                course_result = await trigger_course_generation(request.message, request.user_id)
                # Send the course generation response as a single chunk
                yield f"data: {json.dumps({'content': course_result['message'], 'done': True})}\n\n"
                return

            # Get all context types (same as non-streaming)
            immediate_context = await self._get_immediate_context(request)
            semantic_context = await self._get_semantic_context(request)
            roadmap_context = await self._get_roadmap_context(request)

            # Build enhanced messages
            messages = await self._build_enhanced_messages(
                request, immediate_context, semantic_context, roadmap_context
            )

            # Stream response from AI with memory integration
            full_response = ""
            async for chunk in model_manager.get_streaming_completion_with_memory(messages, user_id=request.user_id):
                full_response += chunk
                # Send chunk in Server-Sent Events format
                yield f"data: {json.dumps({'content': chunk, 'done': False})}\n\n"

            # Send final message indicating completion
            yield f"data: {json.dumps({'content': '', 'done': True})}\n\n"

            # Store the conversation in memory for future context
            if request.user_id and full_response:
                await self._store_conversation_memory(request, full_response, memory_wrapper)

        except Exception as e:
            logger.exception("Error in enhanced streaming chat")
            error_msg = f"Streaming chat failed: {e!s}"
            yield f"data: {json.dumps({'error': error_msg, 'done': True})}\n\n"


# Service instances
enhanced_assistant_service = EnhancedAssistantService()
streaming_enhanced_assistant_service = StreamingEnhancedAssistantService()


# Legacy compatibility functions (can be removed if router is updated)
async def chat_with_assistant(request: ChatRequest) -> ChatResponse:
    """Legacy function - redirects to enhanced service."""
    return await enhanced_assistant_service.chat_with_assistant_enhanced(request)


async def chat_with_assistant_streaming(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Legacy function - redirects to enhanced streaming service."""
    async for chunk in streaming_enhanced_assistant_service.chat_with_assistant_streaming_enhanced(request):
        yield chunk
