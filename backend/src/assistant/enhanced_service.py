"""
Phase 4 Enhanced Assistant Service with Memory Integration and Conversation Management.

This service integrates all Phase 4 features including context-aware memory,
conversation management, and advanced context handling.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID

from src.ai.client import ModelManager
from src.ai.memory import get_memory_wrapper
from src.ai.prompts import ASSISTANT_CHAT_SYSTEM_PROMPT
from src.ai.rag.retriever import ContextAwareRetriever
from src.ai.rag.service import RAGService
from src.database.session import async_session_maker

from .context import ContextManager
from .conversation_manager import get_conversation_manager
from .memory_integration import get_context_aware_memory_manager, get_session_memory_manager
from .schemas import ChatRequest, ChatResponse


logger = logging.getLogger(__name__)


class Phase4AssistantService:
    """Enhanced assistant service with Phase 4 features."""

    def __init__(self) -> None:
        """Initialize the Phase 4 assistant service."""
        self.model_manager = None
        self.memory_wrapper = get_memory_wrapper()
        self.context_manager = ContextManager()
        self.conversation_manager = get_conversation_manager()
        self.context_aware_memory = get_context_aware_memory_manager()
        self.session_memory = get_session_memory_manager()
        self.rag_service = None
        self.context_aware_retriever = None

    async def _get_model_manager(self) -> ModelManager:
        """Get or create model manager instance."""
        if self.model_manager is None:
            self.model_manager = ModelManager(memory_wrapper=self.memory_wrapper)
        return self.model_manager

    async def _get_rag_service(self) -> RAGService:
        """Get or create RAG service instance."""
        if self.rag_service is None:
            async with async_session_maker() as session:
                self.rag_service = RAGService(session)
        return self.rag_service

    async def _get_context_aware_retriever(self) -> ContextAwareRetriever:
        """Get or create context-aware retriever instance."""
        if self.context_aware_retriever is None:
            rag_service = await self._get_rag_service()
            self.context_aware_retriever = ContextAwareRetriever(rag_service)
        return self.context_aware_retriever

    async def chat(self, request: ChatRequest, user_id: str | None = None) -> ChatResponse:
        """
        Enhanced chat with Phase 4 features.

        Args:
            request: Chat request with message and context
            user_id: User identifier for memory and conversation management

        Returns
        -------
            Enhanced chat response with memory integration
        """
        try:
            # Get conversation history with smart pruning
            conversation_history = await self.conversation_manager.prune_context_for_tokens(
                user_id=user_id or "anonymous",
                context_type=request.context_type,
                context_id=request.context_id,
                max_tokens=4000,
                preserve_recent=10,
            )

            # Build enhanced context
            enhanced_context = await self._build_enhanced_context(
                request=request,
                user_id=user_id,
                conversation_history=conversation_history,
            )

            # Prepare messages for AI
            messages = self._prepare_messages(
                request=request,
                conversation_history=conversation_history,
                enhanced_context=enhanced_context,
            )

            # Get AI response
            model_manager = await self._get_model_manager()
            ai_response = await model_manager.chat_completion(
                messages=messages,
                model=request.model,
                temperature=0.7,
                max_tokens=2000,
            )

            response_text = ai_response.get("content", "")

            # Track interaction in memory systems
            await self._track_interaction(
                user_id=user_id,
                request=request,
                response_text=response_text,
            )

            # Add to conversation history
            await self.conversation_manager.add_message(
                user_id=user_id or "anonymous",
                message={"role": "user", "content": request.message},
                context_type=request.context_type,
                context_id=request.context_id,
                token_count=len(request.message) // 4,
            )

            await self.conversation_manager.add_message(
                user_id=user_id or "anonymous",
                message={"role": "assistant", "content": response_text},
                context_type=request.context_type,
                context_id=request.context_id,
                token_count=len(response_text) // 4,
            )

            return ChatResponse(
                response=response_text,
                context_used=bool(enhanced_context),
                model_used=request.model or "default",
            )

        except Exception as e:
            logger.exception(f"Error in Phase 4 chat: {e}")
            raise

    async def chat_stream(self, request: ChatRequest, user_id: str | None = None) -> AsyncGenerator[str, None]:
        """
        Enhanced streaming chat with Phase 4 features.

        Args:
            request: Chat request with message and context
            user_id: User identifier for memory and conversation management

        Yields
        ------
            Streamed response chunks
        """
        try:
            # Get conversation history with smart pruning
            conversation_history = await self.conversation_manager.prune_context_for_tokens(
                user_id=user_id or "anonymous",
                context_type=request.context_type,
                context_id=request.context_id,
                max_tokens=4000,
                preserve_recent=10,
            )

            # Build enhanced context
            enhanced_context = await self._build_enhanced_context(
                request=request,
                user_id=user_id,
                conversation_history=conversation_history,
            )

            # Prepare messages for AI
            messages = self._prepare_messages(
                request=request,
                conversation_history=conversation_history,
                enhanced_context=enhanced_context,
            )

            # Stream AI response
            model_manager = await self._get_model_manager()
            response_chunks = []

            async for chunk in model_manager.chat_completion_stream(
                messages=messages,
                model=request.model,
                temperature=0.7,
                max_tokens=2000,
            ):
                chunk_text = chunk.get("content", "")
                if chunk_text:
                    response_chunks.append(chunk_text)
                    yield chunk_text

            # Combine all chunks for tracking
            full_response = "".join(response_chunks)

            # Track interaction in memory systems
            await self._track_interaction(
                user_id=user_id,
                request=request,
                response_text=full_response,
            )

            # Add to conversation history
            await self.conversation_manager.add_message(
                user_id=user_id or "anonymous",
                message={"role": "user", "content": request.message},
                context_type=request.context_type,
                context_id=request.context_id,
                token_count=len(request.message) // 4,
            )

            await self.conversation_manager.add_message(
                user_id=user_id or "anonymous",
                message={"role": "assistant", "content": full_response},
                context_type=request.context_type,
                context_id=request.context_id,
                token_count=len(full_response) // 4,
            )

        except Exception as e:
            logger.exception(f"Error in Phase 4 streaming chat: {e}")
            yield f"Error: {e!s}"

    async def _build_enhanced_context(
        self,
        request: ChatRequest,
        user_id: str | None,
        conversation_history: list[dict[str, Any]],
    ) -> str:
        """Build enhanced context combining multiple sources."""
        context_parts = []

        try:
            # 1. Get immediate context (Phase 2)
            if request.context_type and request.context_id:
                immediate_context = await self.context_manager.get_context(
                    context_type=request.context_type,
                    resource_id=request.context_id,
                    context_meta=request.context_meta,
                    max_tokens=2000,
                )
                if immediate_context:
                    context_parts.append(f"=== CURRENT CONTEXT ===\n{immediate_context.source}\n{immediate_context.content}")

            # 2. Get RAG context (Phase 3)
            if request.context_type and request.context_id:
                try:
                    retriever = await self._get_context_aware_retriever()
                    rag_results = await retriever.search_with_context(
                        query=request.message,
                        context_type=request.context_type,
                        context_id=request.context_id,
                        limit=5,
                    )
                    if rag_results:
                        rag_context = "\n".join([result.content for result in rag_results])
                        context_parts.append(f"=== RELEVANT MATERIALS ===\n{rag_context}")
                except Exception as e:
                    logger.warning(f"Error retrieving RAG context: {e}")

            # 3. Get hybrid memory context (Phase 4)
            if user_id:
                session_memories = self.session_memory.get_session_memories(user_id)
                memory_context = await self.context_aware_memory.get_hybrid_memory_context(
                    user_id=user_id,
                    current_query=request.message,
                    context_type=request.context_type,
                    context_id=request.context_id,
                    session_memories=session_memories,
                )
                if memory_context:
                    context_parts.append(f"=== PERSONALIZED CONTEXT ===\n{memory_context}")

            # 4. Add conversation context if switching resources
            if user_id and request.context_type and request.context_id:
                switch_history = await self.conversation_manager.get_context_switch_history(user_id)
                if switch_history:
                    recent_switches = switch_history[-3:]  # Last 3 switches
                    if recent_switches:
                        switch_info = []
                        for switch in recent_switches:
                            switch_info.append(f"Switched from {switch['from_resource']} to {switch['to_resource']}")
                        context_parts.append("=== RECENT CONTEXT SWITCHES ===\n" + "\n".join(switch_info))

        except Exception as e:
            logger.exception(f"Error building enhanced context: {e}")

        return "\n\n".join(context_parts) if context_parts else ""

    def _prepare_messages(
        self,
        request: ChatRequest,
        conversation_history: list[dict[str, Any]],
        enhanced_context: str,
    ) -> list[dict[str, str]]:
        """Prepare messages for AI model."""
        messages = []

        # System prompt with enhanced context
        system_prompt = ASSISTANT_CHAT_SYSTEM_PROMPT
        if enhanced_context:
            system_prompt += f"\n\n{enhanced_context}"

        messages.append({"role": "system", "content": system_prompt})

        # Add conversation history (already pruned for tokens)
        for msg in conversation_history:
            if "role" in msg and "content" in msg:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })

        # Add current message
        messages.append({"role": "user", "content": request.message})

        return messages

    async def _track_interaction(
        self,
        user_id: str | None,
        request: ChatRequest,
        response_text: str,
    ) -> None:
        """Track interaction in memory systems."""
        if not user_id:
            return

        try:
            # Track in context-aware memory
            interaction_content = f"User asked: {request.message[:100]}... Assistant responded about: {response_text[:100]}..."
            await self.context_aware_memory.track_context_interaction(
                user_id=user_id,
                interaction_type="assistant_chat",
                content=interaction_content,
                context_type=request.context_type,
                context_id=request.context_id,
                context_meta=request.context_meta,
            )

            # Track in session memory
            self.session_memory.add_session_memory(
                user_id=user_id,
                content=f"Q: {request.message[:50]}... A: {response_text[:50]}...",
                metadata={
                    "context_type": request.context_type,
                    "context_id": str(request.context_id) if request.context_id else None,
                },
            )

        except Exception as e:
            logger.exception(f"Error tracking interaction: {e}")

    async def get_conversation_summary(
        self,
        user_id: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
    ) -> str:
        """Get conversation summary for a specific context."""
        return await self.conversation_manager.get_conversation_summary(
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
        )

    async def get_learning_patterns(
        self,
        user_id: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
    ) -> str:
        """Get learning patterns analysis for a user."""
        return await self.context_aware_memory.get_learning_patterns(
            user_id=user_id,
            context_type=context_type,
            context_id=context_id,
        )

    def get_conversation_stats(self, user_id: str) -> dict[str, Any]:
        """Get conversation statistics for a user."""
        return self.conversation_manager.get_conversation_stats(user_id)


# Global instance
phase4_assistant_service = Phase4AssistantService()


def get_phase4_assistant_service() -> Phase4AssistantService:
    """Get the global Phase 4 assistant service instance."""
    return phase4_assistant_service
