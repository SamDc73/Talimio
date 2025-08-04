"""
Enhanced Memory Integration for Assistant Features.

This module provides context-aware memory management, hybrid memory patterns,
and learning pattern recognition for the AI assistant.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from src.ai.memory import Mem0Wrapper
from src.assistant.context import ContextManager


class ContextAwareMemoryManager:
    """Enhanced memory manager that integrates context data with memory operations."""

    def __init__(self) -> None:
        """Initialize the context-aware memory manager."""
        self.memory_wrapper = Mem0Wrapper()
        self.context_manager = ContextManager()
        self._logger = logging.getLogger(__name__)

    async def add_context_memory(
        self,
        user_id: UUID,
        content: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
        context_meta: dict[str, Any] | None = None,
        interaction_type: str = "assistant_chat",
    ) -> dict[str, Any]:
        """
        Add memory with rich context information.

        Args:
            user_id: User identifier
            content: Memory content
            context_type: Type of context ('book', 'video', 'course')
            context_id: UUID of the resource
            context_meta: Context metadata (page, timestamp, lesson_id, etc.)
            interaction_type: Type of interaction

        Returns
        -------
            Memory entry with enhanced metadata
        """
        try:
            # Build enhanced metadata with context
            enhanced_metadata = {
                "interaction_type": interaction_type,
                "timestamp": datetime.now(UTC).isoformat(),
                "has_context": bool(context_type and context_id),
            }

            # Add context information if available
            if context_type and context_id:
                enhanced_metadata.update(
                    {
                        "context_type": context_type,
                        "context_id": str(context_id),
                    },
                )

                # Add specific context metadata
                if context_meta:
                    if context_type == "book" and "page" in context_meta:
                        enhanced_metadata["page"] = context_meta["page"]
                    elif context_type == "video" and "timestamp" in context_meta:
                        enhanced_metadata["timestamp_seconds"] = context_meta["timestamp"]
                    elif context_type == "course":
                        if "lesson_id" in context_meta:
                            enhanced_metadata["lesson_id"] = context_meta["lesson_id"]
                        if "module_id" in context_meta:
                            enhanced_metadata["module_id"] = context_meta["module_id"]

                # Get current context data for richer memory storage
                context_data = await self.context_manager.get_context(
                    context_type,
                    context_id,
                    context_meta,
                    max_tokens=1000,
                )
                if context_data:
                    enhanced_metadata["context_source"] = context_data.source
                    # Store a snippet of context for better memory retrieval
                    context_snippet = (
                        context_data.content[:200] + "..." if len(context_data.content) > 200 else context_data.content
                    )
                    enhanced_metadata["context_snippet"] = context_snippet

            # Add memory with enhanced metadata
            result = await self.memory_wrapper.add_memory(user_id, content, enhanced_metadata)

            self._logger.info(f"Added context-aware memory for user {user_id} with context {context_type}:{context_id}")
            return result

        except Exception as e:
            self._logger.exception(f"Error adding context memory: {e}")
            # Fallback to basic memory storage
            return await self.memory_wrapper.add_memory(user_id, content, {"interaction_type": interaction_type})

    async def search_context_memories(
        self,
        user_id: UUID,
        query: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
        limit: int = 5,
        relevance_threshold: float = 0.6,
    ) -> list[dict[str, Any]]:
        """
        Search memories with context filtering.

        Args:
            user_id: User identifier
            query: Search query
            context_type: Filter by context type
            context_id: Filter by specific resource
            limit: Maximum results
            relevance_threshold: Minimum relevance score

        Returns
        -------
            List of relevant memories with context information
        """
        try:
            # Enhance query with context information
            enhanced_query = query
            if context_type:
                enhanced_query += f" {context_type}"
            if context_id:
                enhanced_query += f" {context_id}"

            # Search memories
            memories = await self.memory_wrapper.search_memories(
                user_id,
                enhanced_query,
                limit=limit * 2,
                relevance_threshold=relevance_threshold,
            )

            # Filter by context if specified
            if context_type or context_id:
                filtered_memories = []
                for memory in memories:
                    memory_metadata = memory.get("metadata", {})

                    # Check context type match
                    if context_type and memory_metadata.get("context_type") != context_type:
                        continue

                    # Check context ID match
                    if context_id and memory_metadata.get("context_id") != str(context_id):
                        continue

                    filtered_memories.append(memory)

                memories = filtered_memories[:limit]

            self._logger.debug(f"Found {len(memories)} context-filtered memories for user {user_id}")
            return memories

        except Exception as e:
            self._logger.exception(f"Error searching context memories: {e}")
            return []

    async def get_hybrid_memory_context(
        self,
        user_id: UUID,
        current_query: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
        session_memories: list[dict[str, Any]] | None = None,
    ) -> str:
        """
        Build hybrid memory context combining short-term (session) and long-term (persistent) memories.

        Args:
            user_id: User identifier
            current_query: Current query for context
            context_type: Current context type
            context_id: Current context resource ID
            session_memories: Short-term session memories

        Returns
        -------
            Formatted hybrid memory context
        """
        try:
            context_parts = []

            # 1. Get custom instructions (long-term personalization)
            custom_instructions = await self.memory_wrapper.get_custom_instructions(user_id)
            if custom_instructions.strip():
                context_parts.append(f"Personal Learning Preferences:\n{custom_instructions}")

            # 2. Get long-term context-specific memories
            long_term_memories = await self.search_context_memories(
                user_id=user_id,
                query=current_query,
                context_type=context_type,
                context_id=context_id,
                limit=3,
                relevance_threshold=0.4,
            )

            if long_term_memories:
                memory_texts = []
                for memory in long_term_memories:
                    memory_content = memory.get("memory", memory.get("content", ""))
                    metadata = memory.get("metadata", {})
                    context_source = metadata.get("context_source", "")

                    memory_text = memory_content
                    if context_source:
                        memory_text += f" (from {context_source})"

                    memory_texts.append(f"- {memory_text}")

                context_parts.append("Relevant Learning History:\n" + "\n".join(memory_texts))

            # 3. Include short-term session memories
            if session_memories:
                session_texts = []
                for memory in session_memories[-3:]:  # Last 3 session memories
                    content = memory.get("content", memory.get("memory", ""))
                    session_texts.append(f"- {content}")

                if session_texts:
                    context_parts.append("Recent Session Context:\n" + "\n".join(session_texts))

            # 4. Add learning pattern insights
            pattern_insights = await self.get_learning_patterns(user_id, context_type, context_id)
            if pattern_insights:
                context_parts.append(f"Learning Patterns:\n{pattern_insights}")

            return "\n\n".join(context_parts) if context_parts else ""

        except Exception as e:
            self._logger.exception(f"Error building hybrid memory context: {e}")
            return ""

    async def get_learning_patterns(
        self,
        user_id: UUID,
        context_type: str | None = None,
        context_id: UUID | None = None,
    ) -> str:
        """
        Analyze learning patterns from memory data.

        Args:
            user_id: User identifier
            context_type: Context type to analyze
            context_id: Specific resource to analyze

        Returns
        -------
            Learning pattern insights
        """
        try:
            # Get recent memories for pattern analysis
            recent_memories = await self.memory_wrapper.search_memories(
                user_id=user_id,
                query="",  # Get all recent memories
                limit=20,
                relevance_threshold=0.0,
                allow_empty=True,
            )

            if not recent_memories:
                return ""

            # Analyze different pattern types
            usage_patterns = self._analyze_usage_patterns(recent_memories)
            context_patterns = self._analyze_context_specific_patterns(recent_memories, context_type, context_id)

            # Combine all patterns
            all_patterns = usage_patterns + context_patterns

            return "- " + "\n- ".join(all_patterns) if all_patterns else ""

        except Exception as e:
            self._logger.exception(f"Error analyzing learning patterns: {e}")
            return ""

    def _analyze_usage_patterns(self, recent_memories: list[dict]) -> list[str]:
        """Analyze general usage patterns from memory data."""
        patterns = []

        # Initialize pattern counters
        context_types = {}
        interaction_types = {}
        time_patterns = {"morning": 0, "afternoon": 0, "evening": 0}

        # Collect pattern data
        for memory in recent_memories:
            metadata = memory.get("metadata", {})
            self._update_pattern_counters(metadata, context_types, interaction_types, time_patterns)

        # Generate pattern insights
        patterns.extend(self._generate_context_insights(context_types))
        patterns.extend(self._generate_interaction_insights(interaction_types))
        patterns.extend(self._generate_time_insights(time_patterns))

        return patterns

    def _update_pattern_counters(
        self, metadata: dict, context_types: dict, interaction_types: dict, time_patterns: dict
    ) -> None:
        """Update pattern counters from memory metadata."""
        # Count context types
        mem_context_type = metadata.get("context_type", "unknown")
        context_types[mem_context_type] = context_types.get(mem_context_type, 0) + 1

        # Count interaction types
        interaction_type = metadata.get("interaction_type", "unknown")
        interaction_types[interaction_type] = interaction_types.get(interaction_type, 0) + 1

        # Analyze time patterns
        self._analyze_timestamp_pattern(metadata.get("timestamp", ""), time_patterns)

    def _analyze_timestamp_pattern(self, timestamp_str: str, time_patterns: dict) -> None:
        """Analyze timestamp to categorize by time of day."""
        if not timestamp_str:
            return

        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            hour = timestamp.hour
            if 5 <= hour < 12:
                time_patterns["morning"] += 1
            elif 12 <= hour < 18:
                time_patterns["afternoon"] += 1
            else:
                time_patterns["evening"] += 1
        except Exception:
            self._logger.debug("Failed to parse timestamp: %s", timestamp_str)

    def _generate_context_insights(self, context_types: dict) -> list[str]:
        """Generate insights from context type patterns."""
        if not context_types:
            return []

        most_used_context = max(context_types, key=context_types.get)
        if most_used_context != "unknown":
            return [f"Primarily learns from {most_used_context} content"]
        return []

    def _generate_interaction_insights(self, interaction_types: dict) -> list[str]:
        """Generate insights from interaction type patterns."""
        if not interaction_types:
            return []

        most_common_interaction = max(interaction_types, key=interaction_types.get)
        if most_common_interaction != "unknown":
            return [f"Most common interaction: {most_common_interaction}"]
        return []

    def _generate_time_insights(self, time_patterns: dict) -> list[str]:
        """Generate insights from time-based patterns."""
        if not time_patterns:
            return []

        preferred_time = max(time_patterns, key=time_patterns.get)
        if time_patterns[preferred_time] > 0:
            return [f"Most active during {preferred_time}"]
        return []

    def _analyze_context_specific_patterns(
        self, recent_memories: list[dict], context_type: str | None, context_id: UUID | None
    ) -> list[str]:
        """Analyze patterns specific to the current context."""
        if not context_type or not context_id:
            return []

        context_memories = [
            m
            for m in recent_memories
            if m.get("metadata", {}).get("context_type") == context_type
            and m.get("metadata", {}).get("context_id") == str(context_id)
        ]

        if context_memories:
            return [f"Has {len(context_memories)} previous interactions with this {context_type}"]
        return []

    async def track_context_interaction(
        self,
        user_id: UUID,
        interaction_type: str,
        content: str,
        context_type: str | None = None,
        context_id: UUID | None = None,
        context_meta: dict[str, Any] | None = None,
    ) -> None:
        """
        Track learning interactions with full context awareness.

        Args:
            user_id: User identifier
            interaction_type: Type of interaction
            content: Interaction description
            context_type: Context type
            context_id: Context resource ID
            context_meta: Context metadata
        """
        try:
            # Use context-aware memory addition for tracking
            await self.add_context_memory(
                user_id=user_id,
                content=content,
                context_type=context_type,
                context_id=context_id,
                context_meta=context_meta,
                interaction_type=interaction_type,
            )

        except Exception as e:
            self._logger.exception(f"Error tracking context interaction: {e}")


class SessionMemoryManager:
    """Manages short-term session memories."""

    def __init__(self) -> None:
        """Initialize session memory manager."""
        self._session_memories = {}  # user_id -> list of session memories
        self._logger = logging.getLogger(__name__)

    def add_session_memory(self, user_id: UUID, content: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a memory to the current session."""
        if user_id not in self._session_memories:
            self._session_memories[user_id] = []

        memory_entry = {
            "content": content,
            "timestamp": datetime.now(UTC),
            "metadata": metadata or {},
        }

        self._session_memories[user_id].append(memory_entry)

        # Keep only recent session memories (last 20)
        self._session_memories[user_id] = self._session_memories[user_id][-20:]

    def get_session_memories(self, user_id: UUID) -> list[dict[str, Any]]:
        """Get all session memories for a user."""
        return self._session_memories.get(user_id, [])

    def clear_session_memories(self, user_id: UUID) -> None:
        """Clear session memories for a user."""
        if user_id in self._session_memories:
            del self._session_memories[user_id]

    def get_recent_session_context(self, user_id: UUID, limit: int = 5) -> str:
        """Get recent session context as formatted string."""
        memories = self.get_session_memories(user_id)
        if not memories:
            return ""

        recent_memories = memories[-limit:]
        context_parts = []

        for memory in recent_memories:
            timestamp = memory["timestamp"].strftime("%H:%M")
            content = memory["content"]
            context_parts.append(f"[{timestamp}] {content}")

        return "\n".join(context_parts)


# Global instances
context_aware_memory_manager = ContextAwareMemoryManager()
session_memory_manager = SessionMemoryManager()


def get_context_aware_memory_manager() -> ContextAwareMemoryManager:
    """Get the global context-aware memory manager instance."""
    return context_aware_memory_manager


def get_session_memory_manager() -> SessionMemoryManager:
    """Get the global session memory manager instance."""
    return session_memory_manager
