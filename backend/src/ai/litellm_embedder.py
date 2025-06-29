"""Custom LiteLLM embedder for Mem0."""

import os
from typing import Literal

import litellm
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class LiteLLMEmbedding(EmbeddingBase):
    """LiteLLM embedder that supports all LiteLLM-compatible embedding models."""

    def __init__(self, config: BaseEmbedderConfig | None = None):
        super().__init__(config)

        # Default to OpenAI's text-embedding-3-small if no model specified
        self.config.model = self.config.model or os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-3-small")
        self.config.embedding_dims = self.config.embedding_dims or 1536

        # Set up LiteLLM with appropriate API keys
        # LiteLLM will automatically pick up API keys from environment variables

    def embed(self, text: str, memory_action: Literal["add", "search", "update"] | None = None) -> list[float]:
        """
        Get the embedding for the given text using LiteLLM.
        
        Args:
            text: The text to embed.
            memory_action: The type of embedding to use. Not used by LiteLLM.
            
        Returns
        -------
            The embedding vector.
        """
        text = text.replace("\n", " ")

        # Use LiteLLM's embedding function
        response = litellm.embedding(
            model=self.config.model,
            input=[text],
        )

        # Extract the embedding from the response
        return response.data[0]["embedding"]
