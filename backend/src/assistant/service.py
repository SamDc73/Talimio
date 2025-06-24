import logging
from uuid import uuid4

from fastapi import HTTPException, status

from src.ai.client import ModelManager
from src.ai.memory import get_memory_wrapper
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT

from .schemas import ChatRequest, ChatResponse, Citation


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
                        context_parts = []
                        for result in search_results:
                            context_parts.append(f"[Source: {result.document_title}]\n{result.chunk_content}\n")

                            # Add citation
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
