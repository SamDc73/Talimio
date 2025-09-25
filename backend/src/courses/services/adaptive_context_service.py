"""Adaptive context service for building learning context from quiz patterns and memory."""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession


class AdaptiveContextService:
    """Service for building adaptive context for lesson generation.

    This service processes quiz patterns and learning history to create
    context that helps generate personalized, adaptive lesson content.
    """

    def __init__(self, session: AsyncSession, user_id: UUID | None = None) -> None:
        """Initialize the adaptive context service.

        Args:
            session: Database session
            user_id: User ID for user-specific operations
        """
        self.session = session
        self.user_id = user_id
        self._logger = logging.getLogger(__name__)

    async def get_relevant_examples(self, weak_concepts: list[str], limit: int = 3) -> list[dict[str, Any]]:
        """
        Get relevant examples for weak concepts.

        Simply returns the concepts that need examples.
        The AI will generate appropriate examples based on context.

        Args:
            weak_concepts: List of concepts that need reinforcement
            limit: Maximum number of examples to return

        Returns
        -------
            List of example instructions for weak concepts
        """
        # Just return the concepts that need reinforcement
        # Let the AI generate contextually appropriate examples
        return [
            {"concept": concept, "instruction": f"Provide a clear, practical example for {concept}"}
            for concept in weak_concepts[:limit]
        ]

    async def _process_quiz_performance(self, adaptive_context: dict[str, Any], user_id: UUID, course_id: UUID) -> None:
        """Process quiz performance and update adaptive context.

        Fetches recent quiz patterns from mem0 memory to provide context for lesson generation.

        Args:
            adaptive_context: Context dictionary to update
            user_id: User ID
            course_id: Course ID
        """
        from src.ai.memory import search_memories

        try:
            # Get recent quiz performance patterns from mem0
            # Search for recent learning patterns for this course
            recent_patterns = await search_memories(
                user_id=user_id,
                query=f"learning patterns course {course_id} weak concepts performance",
                limit=5,
            )

            if not recent_patterns:
                # No quiz data yet - that's okay, lessons work without it
                return

            # Extract concepts and performance data using helper functions
            weak_concepts, strong_concepts = self._extract_learning_concepts(recent_patterns)
            performance_level = self._determine_performance_level(recent_patterns)

            # Build the pattern for adaptive context
            if weak_concepts or strong_concepts:
                pattern = {
                    "performance_level": performance_level,
                    "weak_concepts": weak_concepts[:3],  # Top 3 weak concepts
                    "strong_concepts": strong_concepts[:3],  # Top 3 strong concepts
                    "learning_velocity": "adaptive",  # We're adapting based on their needs
                }

                adaptive_context["learner_pattern"] = pattern

                # Get examples for weak concepts
                if weak_concepts:
                    examples = await self.get_relevant_examples(weak_concepts[:2], limit=2)
                    if examples:
                        adaptive_context["review_examples"] = examples

                    # Natural review instruction for AI
                    adaptive_context["natural_review"] = {
                        "concepts": weak_concepts[:2],  # Max 2 to keep natural
                        "instruction": (
                            "Naturally reinforce these concepts if they relate to the current lesson topic. "
                            "Use practical examples, analogies, or comparisons to strengthen understanding. "
                            "Don't force unrelated concepts, but weave them in when contextually appropriate."
                        ),
                    }

                # Add encouragement for strong areas
                if strong_concepts:
                    adaptive_context["strengths"] = {
                        "concepts": strong_concepts[:2],
                        "instruction": f"The learner shows strength in {', '.join(strong_concepts[:2])}. Build on these foundations when introducing new concepts.",
                    }

        except Exception as e:
            # Log but don't fail - lessons should work even without quiz data
            self._logger.debug(
                "Could not fetch quiz performance from memory",
                extra={"user_id": str(user_id), "course_id": str(course_id), "error": str(e)},
            )
            # Continue without adaptive context - better than failing

    def _extract_learning_concepts(self, recent_patterns: list[dict]) -> tuple[list[str], list[str]]:
        """Extract weak and strong concepts from memory patterns.

        Args:
            recent_patterns: List of memory patterns from mem0

        Returns
        -------
            Tuple of (weak_concepts, strong_concepts)
        """
        weak_concepts = []
        strong_concepts = []

        for pattern in recent_patterns:
            content = pattern.get("memory", pattern.get("content", ""))

            if "struggles with" in content:
                concept = content.split("struggles with")[1].split("and")[0].strip()
                if concept and concept not in weak_concepts:
                    weak_concepts.append(concept)
            elif "mastered" in content or "excels at" in content:
                concept = (
                    content.split("mastered")[1].strip()
                    if "mastered" in content
                    else content.split("excels at")[1].strip()
                )
                if concept and concept not in strong_concepts:
                    strong_concepts.append(concept)

        return weak_concepts, strong_concepts

    def _determine_performance_level(self, recent_patterns: list[dict]) -> str:
        """Determine overall performance level from recent patterns.

        Args:
            recent_patterns: List of memory patterns from mem0

        Returns
        -------
            Performance level string (proficient, developing, struggling)
        """
        performance_levels = []
        for pattern in recent_patterns:
            metadata = pattern.get("metadata", {})
            if "performance_level" in metadata:
                performance_levels.append(metadata["performance_level"])

        return performance_levels[0] if performance_levels else "developing"

    async def _add_progression_context(self, adaptive_context: dict[str, Any], base_context: dict[str, Any]) -> None:
        """Add progression context from lesson requirements.

        Args:
            adaptive_context: Context dictionary to update
            base_context: Base lesson context
        """
        if "lesson_requirements" not in base_context:
            return

        requirements = base_context["lesson_requirements"]
        if "previous_topics" in requirements:
            adaptive_context["progression"] = {
                "previous": requirements["previous_topics"][:2],  # Limit to 2
                "builds_on": requirements.get("prerequisites", [])[:2],
            }

    async def build_adaptive_context(
        self, base_context: dict[str, Any], user_id: UUID, course_id: UUID | None = None
    ) -> dict[str, Any]:
        """
        Build adaptive context for lesson generation.

        Simple priority-based approach that adds ~500-2000 tokens.
        Integrates mem0 patterns.
        Uses content-based spacing.

        Args:
            base_context: Base lesson context
            user_id: User ID
            course_id: Course ID (optional)

        Returns
        -------
            Adaptive context dictionary for lesson generation
        """
        adaptive_context: dict[str, Any] = {}

        # Priority 1: Get recent performance (if user exists)
        if user_id and course_id:
            await self._process_quiz_performance(adaptive_context, user_id, course_id)

        # Priority 2: Add progression context (what came before/after)
        await self._add_progression_context(adaptive_context, base_context)

        # Priority 3: Integrate mem0 patterns if available
        lesson_title = base_context.get("lesson_title", "")
        if lesson_title and user_id:
            patterns = await self.get_relevant_patterns(user_id, lesson_title, limit=2)
            if patterns:
                # Extract just the content from patterns (keep it simple)
                adaptive_context["learning_history"] = [p.get("memory", p.get("content", "")) for p in patterns]

        return adaptive_context

    async def get_relevant_patterns(self, user_id: UUID, lesson_topic: str, limit: int = 3) -> list[dict[str, Any]]:
        """Use mem0's semantic search to find relevant learning patterns.

        Args:
            user_id: User ID
            lesson_topic: Topic of the lesson to find relevant patterns for
            limit: Maximum number of patterns to return

        Returns
        -------
            List of relevant learning patterns
        """
        from src.ai.memory import search_memories

        # Search for relevant patterns
        patterns = await search_memories(
            user_id=user_id,
            query=f"learning patterns for {lesson_topic}",
            limit=limit * 2,  # Get more to filter
        )

        # Filter to only learning patterns related to the lesson topic
        relevant = []
        for pattern in patterns:
            metadata = pattern.get("metadata", {})
            if metadata.get("type") == "learning_pattern":
                # Check if concept is relevant to lesson topic
                concept = metadata.get("concept", "").lower()
                if concept in lesson_topic.lower() or lesson_topic.lower() in concept:
                    relevant.append(pattern)
                    if len(relevant) >= limit:
                        break

        return relevant
