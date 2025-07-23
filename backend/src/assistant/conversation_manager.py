"""
Conversation Management.

This module provides per-resource conversation history, context switching,
conversation summarization, and smart context pruning.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID


class ConversationManager:
    """Manages conversations with per-resource history and context switching."""

    def __init__(self) -> None:
        """Initialize the conversation manager."""
        self._conversations = {}  # resource_key -> conversation_data
        self._user_sessions = {}  # user_id -> current session data
        self._logger = logging.getLogger(__name__)

    def _get_resource_key(self, context_type: str | None, context_id: UUID | None) -> str:
        """Generate a unique key for resource-specific conversations."""
        if context_type and context_id:
            return f"{context_type}:{context_id}"
        return "global"

    def _get_conversation_data(self, user_id: UUID, resource_key: str) -> dict[str, Any]:
        """Get or create conversation data for a user and resource."""
        conversation_key = f"{user_id}:{resource_key}"

        if conversation_key not in self._conversations:
            self._conversations[conversation_key] = {
                "messages": [],
                "context_switches": [],
                "created_at": datetime.now(),
                "last_activity": datetime.now(),
                "total_tokens": 0,
                "summary": "",
            }

        return self._conversations[conversation_key]

    async def add_message(
        self,
        user_id: UUID,
        message: dict[str, Any],
        context_type: str | None = None,
        context_id: UUID | None = None,
        token_count: int = 0,
    ) -> None:
        """
        Add a message to the appropriate conversation.

        Args:
            user_id: User identifier
            message: Message data (role, content, etc.)
            context_type: Context type ('book', 'video', 'course')
            context_id: Context resource ID
            token_count: Estimated token count for the message
        """
        try:
            resource_key = self._get_resource_key(context_type, context_id)
            conversation_data = self._get_conversation_data(user_id, resource_key)

            # Add timestamp and context info to message
            enhanced_message = {
                **message,
                "timestamp": datetime.now().isoformat(),
                "context_type": context_type,
                "context_id": str(context_id) if context_id else None,
                "token_count": token_count,
            }

            conversation_data["messages"].append(enhanced_message)
            conversation_data["last_activity"] = datetime.now()
            conversation_data["total_tokens"] += token_count

            # Track context switch if switching resources
            await self._track_context_switch(user_id, resource_key, context_type, context_id)

            # Auto-summarize if conversation gets too long
            if len(conversation_data["messages"]) > 50:
                await self._auto_summarize_conversation(user_id, resource_key)

            self._logger.debug(f"Added message to conversation {user_id}:{resource_key}")

        except Exception as e:
            self._logger.exception(f"Error adding message to conversation: {e}")

    async def get_conversation_history(
        self,
        user_id: UUID,
        context_type: str | None = None,
        context_id: UUID | None = None,
        limit: int = 20,
        include_context: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get conversation history for a specific resource.

        Args:
            user_id: User identifier
            context_type: Context type to get history for
            context_id: Context resource ID to get history for
            limit: Maximum number of messages to return
            include_context: Whether to include context information

        Returns
        -------
            List of messages in conversation history
        """
        try:
            resource_key = self._get_resource_key(context_type, context_id)
            conversation_data = self._get_conversation_data(user_id, resource_key)

            messages = conversation_data["messages"][-limit:] if limit > 0 else conversation_data["messages"]

            if not include_context:
                # Remove context-specific fields for cleaner history
                cleaned_messages = []
                for msg in messages:
                    cleaned_msg = {
                        k: v
                        for k, v in msg.items()
                        if k not in ["context_type", "context_id", "token_count", "timestamp"]
                    }
                    cleaned_messages.append(cleaned_msg)
                return cleaned_messages

            return messages

        except Exception as e:
            self._logger.exception(f"Error getting conversation history: {e}")
            return []

    async def _track_context_switch(
        self,
        user_id: UUID,
        new_resource_key: str,
        context_type: str | None,
        context_id: UUID | None,
    ) -> None:
        """Track when a user switches between different resource contexts."""
        try:
            # Get user's current session
            if user_id not in self._user_sessions:
                self._user_sessions[user_id] = {
                    "current_resource": new_resource_key,
                    "session_start": datetime.now(),
                    "context_switches": [],
                }
                return

            session_data = self._user_sessions[user_id]
            current_resource = session_data["current_resource"]

            # Check if this is a context switch
            if current_resource != new_resource_key:
                switch_data = {
                    "from_resource": current_resource,
                    "to_resource": new_resource_key,
                    "timestamp": datetime.now(),
                    "context_type": context_type,
                    "context_id": str(context_id) if context_id else None,
                }

                session_data["context_switches"].append(switch_data)
                session_data["current_resource"] = new_resource_key

                # Add switch record to both conversations
                for resource_key in [current_resource, new_resource_key]:
                    conversation_data = self._get_conversation_data(user_id, resource_key)
                    conversation_data["context_switches"].append(switch_data)

                self._logger.info(f"Context switch: {user_id} from {current_resource} to {new_resource_key}")

        except Exception as e:
            self._logger.exception(f"Error tracking context switch: {e}")

    async def _auto_summarize_conversation(self, user_id: UUID, resource_key: str) -> None:
        """Auto-summarize conversation when it gets too long."""
        try:
            conversation_data = self._get_conversation_data(user_id, resource_key)
            messages = conversation_data["messages"]

            if len(messages) < 30:
                return

            # Simple summarization: keep recent messages and create summary of older ones
            recent_messages = messages[-20:]  # Keep last 20 messages
            older_messages = messages[:-20]  # Summarize older messages

            # Create summary of older messages
            summary_parts = []
            if conversation_data["summary"]:
                summary_parts.append(f"Previous summary: {conversation_data['summary']}")

            # Group older messages by user/assistant pairs
            user_questions = []
            assistant_responses = []

            for msg in older_messages:
                if msg.get("role") == "user":
                    user_questions.append(msg.get("content", ""))
                elif msg.get("role") == "assistant":
                    assistant_responses.append(
                        msg.get("content", "")[:100] + "..."
                        if len(msg.get("content", "")) > 100
                        else msg.get("content", "")
                    )

            if user_questions:
                summary_parts.append(f"User discussed: {'; '.join(user_questions[-5:])}")  # Last 5 questions

            if assistant_responses:
                summary_parts.append(
                    f"Assistant helped with: {'; '.join(assistant_responses[-3:])}"
                )  # Last 3 responses

            # Update conversation data
            conversation_data["summary"] = "\n".join(summary_parts)
            conversation_data["messages"] = recent_messages

            self._logger.info(f"Auto-summarized conversation {user_id}:{resource_key}")

        except Exception as e:
            self._logger.exception(f"Error auto-summarizing conversation: {e}")

    async def get_context_switch_history(self, user_id: UUID) -> list[dict[str, Any]]:
        """Get the history of context switches for a user's session."""
        try:
            session_data = self._user_sessions.get(user_id, {})
            return session_data.get("context_switches", [])

        except Exception as e:
            self._logger.exception(f"Error getting context switch history: {e}")
            return []

    async def get_conversation_summary(
        self,
        user_id: UUID,
        context_type: str | None = None,
        context_id: UUID | None = None,
    ) -> str:
        """Get a summary of the conversation for a specific resource."""
        try:
            resource_key = self._get_resource_key(context_type, context_id)
            conversation_data = self._get_conversation_data(user_id, resource_key)

            summary_parts = []

            # Add existing summary
            if conversation_data["summary"]:
                summary_parts.append(conversation_data["summary"])

            # Add recent activity summary
            messages = conversation_data["messages"]
            if messages:
                recent_user_messages = [msg for msg in messages[-10:] if msg.get("role") == "user"]
                if recent_user_messages:
                    recent_topics = [
                        msg.get("content", "")[:50] + "..."
                        if len(msg.get("content", "")) > 50
                        else msg.get("content", "")
                        for msg in recent_user_messages[-3:]
                    ]
                    summary_parts.append(f"Recent topics: {'; '.join(recent_topics)}")

            # Add context switch information
            if conversation_data["context_switches"]:
                switch_count = len(conversation_data["context_switches"])
                summary_parts.append(f"Context switches: {switch_count}")

            return "\n".join(summary_parts) if summary_parts else "No conversation summary available."

        except Exception as e:
            self._logger.exception(f"Error getting conversation summary: {e}")
            return ""

    async def prune_context_for_tokens(
        self,
        user_id: UUID,
        context_type: str | None = None,
        context_id: UUID | None = None,
        max_tokens: int = 4000,
        preserve_recent: int = 10,
    ) -> list[dict[str, Any]]:
        """
        Smart context pruning to fit within token limits.

        Args:
            user_id: User identifier
            context_type: Context type
            context_id: Context resource ID
            max_tokens: Maximum tokens allowed
            preserve_recent: Number of recent messages to always preserve

        Returns
        -------
            Pruned conversation history that fits within token limits
        """
        try:
            messages = await self.get_conversation_history(
                user_id, context_type, context_id, limit=0, include_context=True
            )

            if not messages:
                return []

            # Always preserve the most recent messages
            recent_messages = messages[-preserve_recent:] if len(messages) > preserve_recent else messages
            older_messages = messages[:-preserve_recent] if len(messages) > preserve_recent else []

            # Calculate tokens for recent messages
            recent_tokens = sum(msg.get("token_count", len(msg.get("content", "")) // 4) for msg in recent_messages)

            # If recent messages already exceed limit, just return them truncated
            if recent_tokens >= max_tokens:
                self._logger.warning(f"Recent messages exceed token limit for {user_id}:{context_type}:{context_id}")
                return recent_messages

            # Add older messages until we reach the token limit
            remaining_tokens = max_tokens - recent_tokens
            selected_older = []

            # Prioritize: important messages (questions, errors) and recent older messages
            prioritized_older = []
            for msg in reversed(older_messages):  # Start from most recent older messages
                content = msg.get("content", "")
                importance_score = 0

                # Higher score for questions
                if msg.get("role") == "user" and (
                    "?" in content or any(word in content.lower() for word in ["how", "what", "why", "when", "where"])
                ):
                    importance_score += 2

                # Higher score for error-related content
                if any(word in content.lower() for word in ["error", "problem", "issue", "help"]):
                    importance_score += 1

                # Higher score for learning-related content
                if any(word in content.lower() for word in ["learn", "understand", "explain", "teach"]):
                    importance_score += 1

                prioritized_older.append((msg, importance_score))

            # Sort by importance score (descending) and add messages until token limit
            prioritized_older.sort(key=lambda x: x[1], reverse=True)

            for msg, score in prioritized_older:
                msg_tokens = msg.get("token_count", len(msg.get("content", "")) // 4)
                if remaining_tokens >= msg_tokens:
                    selected_older.insert(0, msg)  # Insert at beginning to maintain order
                    remaining_tokens -= msg_tokens
                else:
                    break

            # Combine selected older messages with recent messages
            pruned_messages = selected_older + recent_messages

            self._logger.debug(
                f"Pruned conversation from {len(messages)} to {len(pruned_messages)} messages for token limit"
            )
            return pruned_messages

        except Exception as e:
            self._logger.exception(f"Error pruning context for tokens: {e}")
            # Fallback to simple recent message limiting
            return await self.get_conversation_history(
                user_id, context_type, context_id, limit=preserve_recent, include_context=False
            )

    def get_conversation_stats(self, user_id: UUID) -> dict[str, Any]:
        """Get statistics about user's conversations across all resources."""
        try:
            stats = {
                "total_conversations": 0,
                "total_messages": 0,
                "total_tokens": 0,
                "resources": {},
                "context_switches": 0,
            }

            # Collect stats from all conversations for this user
            for conversation_key, conversation_data in self._conversations.items():
                if conversation_key.startswith(f"{user_id}:"):
                    resource_key = conversation_key[len(f"{user_id}:") :]
                    stats["total_conversations"] += 1
                    stats["total_messages"] += len(conversation_data["messages"])
                    stats["total_tokens"] += conversation_data["total_tokens"]
                    stats["context_switches"] += len(conversation_data["context_switches"])

                    stats["resources"][resource_key] = {
                        "messages": len(conversation_data["messages"]),
                        "tokens": conversation_data["total_tokens"],
                        "last_activity": conversation_data["last_activity"].isoformat(),
                    }

            return stats

        except Exception as e:
            self._logger.exception(f"Error getting conversation stats: {e}")
            return {"error": str(e)}

    async def cleanup_old_conversations(self, days_old: int = 30) -> int:
        """Clean up conversations older than specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)
            cleaned_count = 0

            conversations_to_remove = []
            for conversation_key, conversation_data in self._conversations.items():
                if conversation_data["last_activity"] < cutoff_date:
                    conversations_to_remove.append(conversation_key)

            for key in conversations_to_remove:
                del self._conversations[key]
                cleaned_count += 1

            self._logger.info(f"Cleaned up {cleaned_count} old conversations")
            return cleaned_count

        except Exception as e:
            self._logger.exception(f"Error cleaning up old conversations: {e}")
            return 0


# Global instance
conversation_manager = ConversationManager()


def get_conversation_manager() -> ConversationManager:
    """Get the global conversation manager instance."""
    return conversation_manager
