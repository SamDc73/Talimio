import logging
from uuid import uuid4

from fastapi import HTTPException, status

from src.ai.client import ModelManager
from src.ai.memory import get_memory_wrapper
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT

from .schemas import ChatRequest, ChatResponse


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
        )

    except HTTPException:
        raise
    except Exception as e:
        logging.exception("Error in chat with assistant")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Chat failed: {e!s}",
        ) from e
