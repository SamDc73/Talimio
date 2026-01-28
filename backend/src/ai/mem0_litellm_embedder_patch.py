"""Patch mem0 to support LiteLLM-powered embeddings.

Problem
-------
mem0 (v1.0.1 in this repo) supports LiteLLM for *LLMs* but not for *embeddings*.
Talimio wants a single environment variable (`MEMORY_EMBEDDING_MODEL`) to accept
provider-prefixed model names like:

- ``openai/text-embedding-3-small``
- ``ollama/nomic-embed-text``

and have it "just work" via LiteLLM's embedding router.

Approach
--------
mem0 validates the embedder provider against a hard-coded allowlist in
``mem0.embeddings.configs.EmbedderConfig`` (which currently rejects ``litellm``).

To keep configuration compatible without forking mem0, we patch the **existing**
``openai`` embedder provider to use a LiteLLM-backed implementation. This keeps
mem0's config validation happy while allowing the model string itself to route
via LiteLLM (e.g. ``ollama/...``, ``openai/...``, etc.).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Literal

import litellm


try:
    from mem0.configs.embeddings.base import BaseEmbedderConfig
    from mem0.embeddings.base import EmbeddingBase
    from mem0.utils.factory import EmbedderFactory
except Exception:  # pragma: no cover - mem0 is an optional runtime dependency
    BaseEmbedderConfig = object  # type: ignore[assignment]
    EmbeddingBase = object  # type: ignore[assignment]
    EmbedderFactory = None  # type: ignore[assignment]


logger = logging.getLogger(__name__)

_PATCH_APPLIED = False


class Mem0LiteLLMEmbedding(EmbeddingBase):
    """LiteLLM-backed embedder compatible with mem0's EmbeddingBase."""

    def __init__(self, config: BaseEmbedderConfig | None = None) -> None:
        super().__init__(config)
        # Default to the OpenAI embedding model most folks expect.
        self.config.model = self.config.model or "openai/text-embedding-3-small"
        self.config.embedding_dims = self.config.embedding_dims

    def embed(self, text: str, memory_action: Literal["add", "search", "update"] | None = None) -> list[float]:
        """Return embedding vector for input text."""
        del memory_action  # unused by LiteLLM router today

        cleaned = (text or "").replace("\n", " ").strip()
        if not cleaned:
            return []

        kwargs: dict[str, object] = {
            "model": self.config.model,
            "input": [cleaned],
            # Match existing RAG embedder behavior for predictable latency.
            "timeout": 30,
            "max_retries": 0,
        }

        if self.config.embedding_dims:
            # Some providers support this (e.g., OpenAI). Others don't.
            kwargs["dimensions"] = int(self.config.embedding_dims)

        try:
            response = litellm.embedding(**kwargs)
        except Exception as exc:
            # Fallback: if a provider rejects `dimensions`, retry without it once.
            if "dimensions" in kwargs:
                logger.debug("LiteLLM embedding failed with dimensions, retrying without. err=%s", exc)
                kwargs.pop("dimensions", None)
                response = litellm.embedding(**kwargs)
            else:
                raise

        data = getattr(response, "data", None)
        if isinstance(data, Sequence) and data:
            item = data[0]
            embedding = item.get("embedding") if isinstance(item, dict) else getattr(item, "embedding", None)
        else:
            embedding = None

        if not isinstance(embedding, Sequence) or isinstance(embedding, (str, bytes)):
            msg = f"Unexpected LiteLLM embedding response shape: {type(response)}"
            raise TypeError(msg)

        return [float(value) for value in embedding]


def apply_mem0_litellm_embedder_patch() -> None:
    """Route mem0's ``openai`` embedder provider through LiteLLM (idempotent)."""
    global _PATCH_APPLIED  # noqa: PLW0603

    if _PATCH_APPLIED:
        return

    if EmbedderFactory is None:
        logger.debug("mem0 not importable; skipping LiteLLM embedder patch")
        return

    # mem0's pydantic config currently rejects embedder.provider='litellm', so
    # we patch an allowed provider to keep things "just work" without vendoring mem0.
    EmbedderFactory.provider_to_class["openai"] = "src.ai.mem0_litellm_embedder_patch.Mem0LiteLLMEmbedding"
    _PATCH_APPLIED = True
    logger.info("Applied mem0 LiteLLM embedder patch (embedder provider 'openai' routed via LiteLLM)")
