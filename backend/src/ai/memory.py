"""
AI Memory & Personalization Service using Mem0 OSS.

This module provides memory management and custom instructions for AI personalization
across all AI endpoints in the learning roadmap platform.
"""

import logging
import os
from typing import Any

import asyncpg
from mem0 import Memory

from src.config.settings import get_settings


class AIMemoryError(Exception):
    """Base exception for memory-related errors."""


class Mem0Wrapper:
    """
    Wrapper for Mem0 AI memory system with pgvector and custom instructions.

    Handles both vector-based memory storage and custom user instructions
    for comprehensive AI personalization.
    """

    def __init__(self) -> None:
        """Initialize Mem0 with pgvector configuration."""
        self.settings = get_settings()
        self._logger = logging.getLogger(__name__)
        self._memory_client = None
        self._db_pool = None

        # Mem0 configuration for production with pgvector
        self.config = {
            "vector_store": {
                "provider": "pgvector",
                "config": {
                    "dbname": os.getenv("DB_NAME", "neondb"),
                    "user": self._extract_db_user(),
                    "password": self._extract_db_password(),
                    "host": self._extract_db_host(),
                    "port": self._extract_db_port(),
                    "collection_name": "learning_memories"
                }
            },
            "llm": {
                "provider": "litellm",
                "config": {
                    "model": os.getenv("MEMORY_LLM_MODEL", "openai/gpt-4o-mini"),
                    "temperature": 0.2,
                    "max_tokens": 2000
                }
            },
            "embedder": {
                "provider": "litellm",
                "config": {
                    "model": os.getenv("MEMORY_EMBEDDING_MODEL", "huggingface/sentence-transformers/all-MiniLM-L6-v2")
                }
            }
        }

    def _extract_db_user(self) -> str:
        """Extract database user from DATABASE_URL."""
        database_url = os.getenv("DATABASE_URL", "")
        if "://" in database_url:
            # Extract from URL format: postgresql+asyncpg://user:pass@host:port/db
            auth_part = database_url.split("://")[1].split("@")[0]
            return auth_part.split(":")[0]
        return os.getenv("DB_USER", "postgres")

    def _extract_db_password(self) -> str:
        """Extract database password from DATABASE_URL."""
        database_url = os.getenv("DATABASE_URL", "")
        if "://" in database_url:
            auth_part = database_url.split("://")[1].split("@")[0]
            if ":" in auth_part:
                return auth_part.split(":", 1)[1]
        return os.getenv("DB_PASSWORD", "")

    def _extract_db_host(self) -> str:
        """Extract database host from DATABASE_URL."""
        database_url = os.getenv("DATABASE_URL", "")
        if "://" in database_url:
            host_part = database_url.split("@")[1].split("/")[0]
            return host_part.split(":")[0]
        return os.getenv("DB_HOST", "localhost")

    def _extract_db_port(self) -> str:
        """Extract database port from DATABASE_URL."""
        database_url = os.getenv("DATABASE_URL", "")
        if "://" in database_url:
            host_part = database_url.split("@")[1].split("/")[0]
            if ":" in host_part:
                return host_part.split(":")[1]
        return os.getenv("DB_PORT", "5432")

    @property
    def memory_client(self) -> Memory:
        """Get or create Mem0 client instance."""
        if self._memory_client is None:
            try:
                self._memory_client = Memory(config=self.config)
                self._logger.info("Mem0 client initialized successfully")
            except Exception as e:
                self._logger.exception(f"Failed to initialize Mem0 client: {e}")
                # Create a fallback mock client for development
                self._memory_client = self._create_fallback_client()
        return self._memory_client

    def _create_fallback_client(self) -> Any:
        """Create a fallback client when Mem0 initialization fails."""
        class FallbackMemory:
            def add(self, *_args: Any, **_kwargs: Any) -> dict[str, Any]:
                return {"id": "fallback", "memory": "Memory storage temporarily unavailable"}

            def search(self, *_args: Any, **_kwargs: Any) -> list[dict[str, Any]]:
                return []

            def delete_all(self, *_args: Any, **_kwargs: Any) -> dict[str, str]:
                return {"message": "Memory cleared (fallback mode)"}

        self._logger.warning("Using fallback memory client - memory features disabled")
        return FallbackMemory()

    async def _get_db_connection(self) -> asyncpg.Connection:
        """Get database connection for custom instructions."""
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            asyncpg_url = database_url.replace("postgresql+asyncpg://", "postgresql://")
            return await asyncpg.connect(asyncpg_url)
        # Fallback to environment variables
        return await asyncpg.connect(
            host=self._extract_db_host(),
            port=int(self._extract_db_port()),
            user=self._extract_db_user(),
            password=self._extract_db_password(),
            database=os.getenv("DB_NAME", "neondb")
        )

    async def add_memory(self, user_id: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Add a memory entry for a user.

        Args:
            user_id: Unique identifier for the user
            content: Content to store in memory
            metadata: Additional metadata (learning context, topic, etc.)

        Returns
        -------
            Memory entry with ID and stored content
        """
        try:
            if metadata is None:
                metadata = {}

            # Add user context to metadata
            metadata.update({
                "user_id": user_id,
                "timestamp": metadata.get("timestamp", "now"),
                "source": metadata.get("source", "learning_platform")
            })

            result = self.memory_client.add(
                content,
                user_id=user_id,
                metadata=metadata
            )

            self._logger.debug(f"Added memory for user {user_id}: {content[:100]}...")
            return result

        except Exception as e:
            self._logger.exception(f"Error adding memory for user {user_id}: {e}")
            msg = f"Failed to add memory: {e}"
            raise AIMemoryError(msg) from e

    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
        relevance_threshold: float = 0.7
    ) -> list[dict[str, Any]]:
        """
        Search for relevant memories for a user.

        Args:
            user_id: Unique identifier for the user
            query: Search query to find relevant memories
            limit: Maximum number of memories to return
            relevance_threshold: Minimum relevance score (0.0-1.0)

        Returns
        -------
            List of relevant memory entries with content and metadata
        """
        try:
            results = self.memory_client.search(
                query=query,
                user_id=user_id,
                limit=limit
            )

            # Filter by relevance threshold if specified
            filtered_results = []
            for result in results:
                score = result.get("score", 1.0)  # Default high score if not provided
                if score >= relevance_threshold:
                    filtered_results.append(result)

            self._logger.debug(f"Found {len(filtered_results)} relevant memories for user {user_id}")
            return filtered_results

        except Exception as e:
            self._logger.exception(f"Error searching memories for user {user_id}: {e}")
            return []  # Return empty list on error to not break AI responses

    async def delete_all_memories(self, user_id: str) -> dict[str, str]:
        """
        Delete all memories for a user.

        Args:
            user_id: Unique identifier for the user

        Returns
        -------
            Confirmation message
        """
        try:
            result = self.memory_client.delete_all(user_id=user_id)
            self._logger.info(f"Deleted all memories for user {user_id}")
            return result

        except Exception as e:
            self._logger.exception(f"Error deleting memories for user {user_id}: {e}")
            msg = f"Failed to delete memories: {e}"
            raise AIMemoryError(msg) from e

    async def get_custom_instructions(self, user_id: str) -> str:
        """
        Get custom instructions for a user.

        Args:
            user_id: Unique identifier for the user

        Returns
        -------
            User's custom instructions or empty string
        """
        try:
            conn = await self._get_db_connection()
            try:
                result = await conn.fetchrow(
                    "SELECT instructions FROM user_custom_instructions WHERE user_id = $1",
                    user_id
                )
                return result["instructions"] if result else ""
            finally:
                await conn.close()

        except Exception as e:
            self._logger.exception(f"Error getting custom instructions for user {user_id}: {e}")
            return ""  # Return empty string on error

    async def update_custom_instructions(self, user_id: str, instructions: str) -> bool:
        """
        Update custom instructions for a user.

        Args:
            user_id: Unique identifier for the user
            instructions: Custom instructions text

        Returns
        -------
            True if successful, False otherwise
        """
        try:
            conn = await self._get_db_connection()
            try:
                await conn.execute("""
                    INSERT INTO user_custom_instructions (user_id, instructions, updated_at)
                    VALUES ($1, $2, NOW())
                    ON CONFLICT (user_id)
                    DO UPDATE SET instructions = $2, updated_at = NOW()
                """, user_id, instructions)

                self._logger.info(f"Updated custom instructions for user {user_id}")
                return True
            finally:
                await conn.close()

        except Exception as e:
            self._logger.exception(f"Error updating custom instructions for user {user_id}: {e}")
            return False

    async def build_memory_context(self, user_id: str, current_query: str) -> str:
        """
        Build memory context for AI prompts by combining custom instructions and relevant memories.

        Args:
            user_id: Unique identifier for the user
            current_query: Current user query/context for memory search

        Returns
        -------
            Formatted context string for AI prompts
        """
        try:
            # Get custom instructions
            custom_instructions = await self.get_custom_instructions(user_id)

            # Search for relevant memories
            relevant_memories = await self.search_memories(
                user_id=user_id,
                query=current_query,
                limit=5
            )

            # Build context string
            context_parts = []

            if custom_instructions.strip():
                context_parts.append(f"User's Custom Instructions:\n{custom_instructions}")

            if relevant_memories:
                memory_texts = []
                for memory in relevant_memories:
                    memory_content = memory.get("memory", memory.get("content", ""))
                    if memory_content:
                        memory_texts.append(f"- {memory_content}")

                if memory_texts:
                    context_parts.append("Relevant Learning History:\n" + "\n".join(memory_texts))

            return "\n\n".join(context_parts) if context_parts else ""

        except Exception as e:
            self._logger.exception(f"Error building memory context for user {user_id}: {e}")
            return ""  # Return empty context on error to not break AI responses

    async def track_learning_interaction(
        self,
        user_id: str,
        interaction_type: str,
        content: str,
        metadata: dict[str, Any] | None = None
    ) -> None:
        """
        Track learning interactions automatically (behind the scenes).

        Args:
            user_id: Unique identifier for the user
            interaction_type: Type of interaction (chat, lesson_completion, roadmap_creation, etc.)
            content: Description of the interaction
            metadata: Additional context (topic, difficulty, completion_time, etc.)
        """
        try:
            if metadata is None:
                metadata = {}

            metadata.update({
                "interaction_type": interaction_type,
                "auto_tracked": True
            })

            await self.add_memory(user_id, content, metadata)

        except Exception as e:
            # Log error but don't raise - tracking failures shouldn't break user experience
            self._logger.exception(f"Error tracking interaction for user {user_id}: {e}")


# Global instance for dependency injection
memory_wrapper = Mem0Wrapper()


def get_memory_wrapper() -> Mem0Wrapper:
    """Dependency injection for memory wrapper."""
    return memory_wrapper
