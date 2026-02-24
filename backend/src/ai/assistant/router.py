"""Assistant API router - simple chat endpoint."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse

from src.auth import CurrentAuth
from src.config.settings import get_settings

from . import conversations_service, service as assistant_service
from .schemas import (
    AppendConversationHistoryResponse,
    ChatRequest,
    ConversationHistoryItemRequest,
    ConversationHistoryItemResponse,
    ConversationHistoryResponse,
    ConversationListResponse,
    ConversationThreadResponse,
    CreateConversationRequest,
    CreateConversationResponse,
    RenameConversationRequest,
)


router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


@router.post("/chat")
async def assistant_chat(
    request: ChatRequest,
    auth: CurrentAuth,
) -> StreamingResponse:
    """Stream chat responses from the AI assistant."""
    return StreamingResponse(
        assistant_service.assistant_chat(request, user_id=auth.user_id, session=auth.session),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "x-vercel-ai-ui-message-stream": "v1",
        },
    )


@router.post("/conversations", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    request: CreateConversationRequest,
    auth: CurrentAuth,
) -> CreateConversationResponse:
    """Create a new assistant conversation."""
    try:
        conversation = await conversations_service.create_assistant_conversation(
            session=auth.session,
            user_id=auth.user_id,
            title=request.title,
            context_type=request.context_type,
            context_id=request.context_id,
            context_meta=request.context_meta,
        )
    except conversations_service.AssistantConversationValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    return CreateConversationResponse(remoteId=conversation.id)


@router.get("/conversations")
async def list_conversations(
    auth: CurrentAuth,
    page: Annotated[int, Query(ge=1)] = 1,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ConversationListResponse:
    """List assistant conversations ordered by most recent update."""
    items, total = await conversations_service.list_assistant_conversations(
        session=auth.session,
        user_id=auth.user_id,
        page=page,
        limit=limit,
    )
    return ConversationListResponse(
        items=[ConversationThreadResponse.model_validate(item) for item in items],
        page=page,
        limit=limit,
        total=total,
    )


@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: uuid.UUID,
    auth: CurrentAuth,
) -> ConversationThreadResponse:
    """Get one assistant conversation metadata payload."""
    try:
        payload = await conversations_service.get_assistant_conversation_with_summary(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return ConversationThreadResponse.model_validate(payload)


@router.patch("/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: uuid.UUID,
    request: RenameConversationRequest,
    auth: CurrentAuth,
) -> ConversationThreadResponse:
    """Rename an assistant conversation."""
    try:
        await conversations_service.rename_assistant_conversation(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
            title=request.title,
        )
        payload = await conversations_service.get_assistant_conversation_with_summary(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return ConversationThreadResponse.model_validate(payload)


@router.post("/conversations/{conversation_id}/archive")
async def archive_conversation(
    conversation_id: uuid.UUID,
    auth: CurrentAuth,
) -> ConversationThreadResponse:
    """Archive an assistant conversation."""
    try:
        await conversations_service.archive_assistant_conversation(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
        payload = await conversations_service.get_assistant_conversation_with_summary(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return ConversationThreadResponse.model_validate(payload)


@router.post("/conversations/{conversation_id}/unarchive")
async def unarchive_conversation(
    conversation_id: uuid.UUID,
    auth: CurrentAuth,
) -> ConversationThreadResponse:
    """Restore an assistant conversation to regular status."""
    try:
        await conversations_service.unarchive_assistant_conversation(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
        payload = await conversations_service.get_assistant_conversation_with_summary(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return ConversationThreadResponse.model_validate(payload)


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    auth: CurrentAuth,
) -> Response:
    """Delete an assistant conversation and its history."""
    try:
        await conversations_service.delete_assistant_conversation(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/conversations/{conversation_id}/history")
async def get_conversation_history(
    conversation_id: uuid.UUID,
    auth: CurrentAuth,
) -> ConversationHistoryResponse:
    """Load exported assistant-ui history for one conversation."""
    try:
        payload = await conversations_service.load_assistant_conversation_history(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error

    return ConversationHistoryResponse(
        head_id=payload["head_id"],
        messages=[ConversationHistoryItemResponse.model_validate(item) for item in payload["messages"]],
    )


@router.post("/conversations/{conversation_id}/history")
async def append_conversation_history_item(
    conversation_id: uuid.UUID,
    request: ConversationHistoryItemRequest,
    auth: CurrentAuth,
) -> AppendConversationHistoryResponse:
    """Append one assistant-ui history item with idempotent insert semantics."""
    try:
        inserted = await conversations_service.append_assistant_conversation_history_item(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
            message=request.message,
            parent_id=request.parent_id,
            run_config=request.run_config,
        )
        conversation = await conversations_service.get_assistant_conversation(
            session=auth.session,
            user_id=auth.user_id,
            conversation_id=conversation_id,
        )
    except conversations_service.AssistantConversationNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except conversations_service.AssistantConversationValidationError as error:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(error)) from error

    return AppendConversationHistoryResponse(
        appended=inserted,
        head_id=conversation.head_message_id,
    )


@router.get("/models")
async def get_models() -> dict[str, list[dict[str, Any]]]:
    """Return list of available assistant models.

    Minimal payload for UI model picker:
    - id: full model identifier (e.g., "gpt-5-nano")
    - isDefault: whether this is the primary model
    """
    # Ensure settings/env are loaded
    settings = get_settings()

    primary = settings.primary_llm_model
    available_raw = settings.AVAILABLE_MODELS
    available = [m.strip() for m in available_raw.split(",") if m.strip()] if available_raw else []

    # Build ordered unique list with primary first
    ordered = [primary, *available]
    seen: set[str] = set()
    models: list[dict[str, Any]] = []

    for i, model_id in enumerate(ordered):
        if model_id in seen:
            continue
        models.append({
            "id": model_id,
            "isDefault": i == 0,
        })
        seen.add(model_id)

    return {"models": models}
