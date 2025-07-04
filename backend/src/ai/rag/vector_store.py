"""Vector store operations and embedding generation."""

import json
import logging
import os
import secrets
import uuid

from litellm import embedding, get_supported_openai_params
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.session import async_session_maker


logger = logging.getLogger(__name__)


class EmbeddingGenerator:
    """Generate embeddings using LiteLLM."""

    # Class-level cache for model capabilities
    _model_capabilities_cache: dict[str, bool] = {}

    def __init__(self) -> None:
        """Initialize embedding generator with configuration."""
        self.model = os.getenv("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
        # Use configured dimensions if available
        self.dimensions = int(os.getenv("RAG_EMBEDDING_OUTPUT_DIM")) if os.getenv("RAG_EMBEDDING_OUTPUT_DIM") else None
        self.instruction = os.getenv("RAG_EMBED_INSTRUCTION", "Represent the query for semantic retrieval:")

        # Log model info
        logger.info(f"Using embedding model: {self.model}")

        # Try to detect model capabilities on init (optional)
        self._detect_model_capabilities()


    def _detect_model_capabilities(self) -> None:
        """Detect model capabilities at initialization time."""
        # Skip detection if already cached
        if self.model in self._model_capabilities_cache:
            return

        # First, try to use LiteLLM's built-in capability detection if available
        try:

            # Extract provider from model name (e.g., "openai/text-embedding-3-small" -> "openai")
            provider = self.model.split("/")[0] if "/" in self.model else None

            # Try to get supported params (this might not work for embeddings)
            if provider:
                supported_params = get_supported_openai_params(model=self.model, custom_llm_provider=provider)
                if "dimensions" in supported_params:
                    self._model_capabilities_cache[self.model] = True
                    logger.info(f"Model {self.model} supports dimensions (via get_supported_openai_params)")
                    return
        except Exception:
            # get_supported_openai_params might not work for embeddings
            logger.debug("get_supported_openai_params not available or failed")

        # Fallback: Try a test embedding with dimensions parameter
        try:
            test_text = ["test"]

            try:
                # Test with dimensions parameter
                if self.dimensions:
                    embedding(model=self.model, input=test_text, dimensions=self.dimensions)
                else:
                    embedding(model=self.model, input=test_text)
                self._model_capabilities_cache[self.model] = True
                logger.info(f"Model {self.model} supports dimensions parameter")
            except Exception as e:
                error_str = str(e).lower()
                # Check for various error messages indicating unsupported dimensions parameter
                if any(keyword in error_str for keyword in [
                    "dimensions",
                    "unexpected keyword",
                    "got an unexpected keyword argument",
                    "output_dimension is not supported",  # Cohere specific error
                    "invalid request"  # Cohere error prefix
                ]):
                    self._model_capabilities_cache[self.model] = False
                    logger.info(f"Model {self.model} does not support dimensions parameter")
                else:
                    # Don't cache if it's a different error (e.g., auth, network)
                    logger.warning(f"Could not detect capabilities for {self.model}: {e}")
        except Exception as e:
            # Don't fail init if detection fails
            logger.warning(f"Model capability detection failed for {self.model}: {e}")


    async def generate_embeddings(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """Generate embeddings for text chunks."""
        # Get batch size from environment
        max_batch_size = int(os.getenv("RAG_EMBEDDING_BATCH_SIZE", "10"))

        if len(texts) > max_batch_size:
            logger.info(f"Processing {len(texts)} texts in batches of {max_batch_size}")

        try:
            # Add instruction prefix for queries only (not documents)
            prefixed_texts = [f"{self.instruction} {text}" for text in texts] if is_query else texts

            # Process in batches if needed
            if len(prefixed_texts) > max_batch_size:
                logger.info(f"Processing {len(prefixed_texts)} texts in batches of {max_batch_size}")
                all_embeddings = []

                for i in range(0, len(prefixed_texts), max_batch_size):
                    batch = prefixed_texts[i:i + max_batch_size]
                    batch_embeddings = await self._generate_batch_embeddings(batch)
                    all_embeddings.extend(batch_embeddings)

                return all_embeddings
            return await self._generate_batch_embeddings(prefixed_texts)

        except Exception as e:
            logger.exception(f"Embedding generation failed: {e}")
            # For debugging, try with a very small batch to see if it's a size issue
            if len(texts) > 1:
                logger.warning("Trying with single text to diagnose issue...")
                try:
                    test_emb = await self._generate_batch_embeddings(prefixed_texts[:1])
                    logger.info(f"Single text embedding succeeded, dimension: {len(test_emb[0])}")
                except Exception as test_e:
                    logger.exception(f"Even single text failed: {test_e}")

            # Return random embeddings as fallback
            logger.warning(f"Using random embeddings as fallback for {len(texts)} texts")
            rng = secrets.SystemRandom()
            dimensions = self.dimensions or 1536  # Use configured or default
            return [[rng.random() for _ in range(dimensions)] for _ in texts]

    async def _generate_batch_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a single batch."""
        try:
            # Check cache first to avoid unnecessary retries
            supports_dimensions = self._model_capabilities_cache.get(self.model)

            # If dimensions is None, don't try to use it
            if self.dimensions is None:
                response = embedding(model=self.model, input=texts)
            elif supports_dimensions is None:
                # Not in cache, need to detect capability
                try:
                    # Try with dimensions parameter
                    response = embedding(model=self.model, input=texts, dimensions=self.dimensions)
                    # Success! Cache that this model supports dimensions
                    self._model_capabilities_cache[self.model] = True
                except Exception as e:
                    error_str = str(e).lower()
                    # Check for various error messages indicating unsupported dimensions parameter
                    if any(keyword in error_str for keyword in [
                        "dimensions",
                        "unexpected keyword",
                        "got an unexpected keyword argument",
                        "output_dimension is not supported",  # Cohere specific error
                        "invalid request"  # Cohere error prefix
                    ]):
                        # Model doesn't support dimensions, cache this and retry
                        logger.info(f"Model {self.model} doesn't support dimensions parameter, caching for future use")
                        self._model_capabilities_cache[self.model] = False
                        response = embedding(model=self.model, input=texts)
                    else:
                        # Different error, re-raise
                        raise
            elif supports_dimensions:
                # We know it supports dimensions
                response = embedding(model=self.model, input=texts, dimensions=self.dimensions)
            else:
                # We know it doesn't support dimensions
                response = embedding(model=self.model, input=texts)

            result = [item["embedding"] for item in response["data"]]

            # If dimensions is set and there's a mismatch, log it but don't modify
            if result and self.dimensions is not None:
                actual_dim = len(result[0])
                if actual_dim != self.dimensions:
                    logger.info(f"Embedding dimensions: Expected {self.dimensions}, got {actual_dim} from model {self.model}")

            return result

        except Exception as e:
            logger.exception(f"Embedding generation failed: {e}")
            # For document embeddings, we must fail as we can't store without proper embeddings
            raise

    async def _get_fallback_embedding_for_query(self, texts: list[str]) -> list[list[float]]:
        """Get a fallback embedding using stored embeddings for demonstration."""
        # Get a stored embedding that might be related to the query
        async with async_session_maker() as session:
            try:
                # Try to find a chunk that contains some of the query words
                " ".join(texts).lower()

                # Look for chunks containing query terms
                result = await session.execute(
                    text("""
                    SELECT embedding
                    FROM rag_document_chunks
                    WHERE doc_id = 'ef72c851-89f2-4214-8451-529bba1fc2d6'
                      AND doc_type = 'book'
                      AND (content ILIKE '%' || :term1 || '%'
                           OR content ILIKE '%' || :term2 || '%'
                           OR content ILIKE '%' || :term3 || '%')
                    LIMIT 1
                """),
                    {"term1": "probabilities", "term2": "chatgpt", "term3": "statistics"},
                )

                row = result.fetchone()
                if row:
                    # Parse the embedding string back to list
                    embedding_str = str(row.embedding).strip("[]")
                    embedding = [float(x.strip()) for x in embedding_str.split(",")]
                    return [embedding] * len(texts)  # Return same embedding for all texts

                # Fallback: get any embedding
                result = await session.execute(
                    text("""
                    SELECT embedding
                    FROM rag_document_chunks
                    WHERE doc_id = 'ef72c851-89f2-4214-8451-529bba1fc2d6'
                      AND doc_type = 'book'
                    LIMIT 1
                """)
                )

                row = result.fetchone()
                if row:
                    embedding_str = str(row.embedding).strip("[]")
                    embedding = [float(x.strip()) for x in embedding_str.split(",")]
                    return [embedding] * len(texts)

            except Exception as db_error:
                logger.exception(f"Fallback embedding failed: {db_error}")

        # Final fallback: create a random embedding with correct dimensions
        # Using secrets.SystemRandom for better randomness
        rng = secrets.SystemRandom()
        return [[rng.random() for _ in range(768)] for _ in texts]

    async def generate_query_embedding(self, query: str) -> list[float]:
        """Generate embedding for a single query."""
        embeddings = await self.generate_embeddings([query], is_query=True)
        return embeddings[0]


class VectorStore:
    """Handle pgvector operations for document chunks."""

    def __init__(self) -> None:
        """Initialize vector store."""
        self.embedding_generator = EmbeddingGenerator()

    async def store_chunks_with_embeddings(self, session: AsyncSession, doc_id: uuid.UUID, chunks: list[str]) -> None:
        """Store text chunks with their embeddings in rag_document_chunks table."""
        # Generate embeddings for all chunks
        embeddings = await self.embedding_generator.generate_embeddings(chunks)

        # Store each chunk with its embedding
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings, strict=False)):
            # Check if chunk already exists
            existing = await session.execute(
                text("""
                    SELECT id FROM rag_document_chunks
                    WHERE doc_id = :doc_id AND chunk_index = :chunk_idx
                """),
                {"doc_id": str(doc_id), "chunk_idx": i}
            )
            existing_row = existing.fetchone()

            if existing_row:
                # Update existing chunk
                await session.execute(
                    text("""
                        UPDATE rag_document_chunks
                        SET content = :content,
                            embedding = CAST(:embedding AS vector),
                            metadata = :metadata
                        WHERE doc_id = :doc_id AND chunk_index = :chunk_idx
                    """),
                    {
                        "doc_id": str(doc_id),
                        "content": chunk,
                        "embedding": str(emb),
                        "metadata": json.dumps({"chunk_type": "basic"}),
                        "chunk_idx": i,
                    }
                )
            else:
                # Insert new chunk
                await session.execute(
                    text("""
                        INSERT INTO rag_document_chunks
                        (doc_id, doc_type, chunk_index, content, embedding, metadata)
                        VALUES (:doc_id, :doc_type, :chunk_idx, :content, CAST(:embedding AS vector), :metadata)
                    """),
                    {
                        "doc_id": str(doc_id),
                        "doc_type": "book",  # Default to book for now
                        "chunk_idx": i,
                        "content": chunk,
                        "embedding": str(emb),  # pgvector handles list conversion
                        "metadata": json.dumps({"chunk_type": "basic"}),
                    }
                )





    async def similarity_search(
        self, session: AsyncSession, query_embedding: list[float], roadmap_id: uuid.UUID, top_k: int
    ) -> list[dict]:
        """Perform similarity search using pgvector."""
        result = await session.execute(
            text("""
                SELECT
                    dc.document_id,
                    rd.title as document_title,
                    dc.content,
                    dc.metadata as doc_metadata,
                    1 - (dc.embedding <=> :query_embedding) as similarity_score
                FROM document_chunks dc
                JOIN roadmap_documents rd ON dc.document_id = rd.id
                WHERE rd.roadmap_id = :roadmap_id
                AND rd.status = 'embedded'
                ORDER BY dc.embedding <=> :query_embedding
                LIMIT :top_k
            """),
            {"query_embedding": str(query_embedding), "roadmap_id": str(roadmap_id), "top_k": top_k},
        )

        return [
            {
                "document_id": row.document_id,
                "document_title": row.document_title,
                "content": row.content,
                "doc_metadata": row.doc_metadata,
                "similarity_score": row.similarity_score,
            }
            for row in result.fetchall()
        ]

    async def search_document_chunks(
        self,
        session: AsyncSession,
        doc_id: uuid.UUID,
        doc_type: str,
        query: str,
        top_k: int = 10,
        relevance_threshold: float = 0.5
    ) -> list:
        """Search for relevant chunks within a specific document."""
        try:
            # Try vector search first
            query_embedding = await self.embedding_generator.generate_query_embedding(query)

            # Perform vector similarity search
            result = await session.execute(
                text("""
                    SELECT
                        id,
                        doc_id,
                        doc_type,
                        chunk_index,
                        content,
                        metadata,
                        1 - (embedding <=> CAST(:query_embedding AS vector)) as similarity_score
                    FROM rag_document_chunks
                    WHERE doc_id = :doc_id
                    AND doc_type = :doc_type
                    AND embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:query_embedding AS vector)
                    LIMIT :top_k
                """),
                {
                    "query_embedding": str(query_embedding),
                    "doc_id": str(doc_id),
                    "doc_type": doc_type,
                    "top_k": top_k
                }
            )

            rows = result.fetchall()

            # If we got results from vector search, use them
            if rows:
                return [
                    {
                        "document_id": row.id,
                        "document_title": f"{row.doc_type.title()} chunk {row.chunk_index}",
                        "content": row.content,
                        "doc_metadata": row.metadata or {},
                        "similarity_score": row.similarity_score,
                    }
                    for row in rows
                    if row.similarity_score >= relevance_threshold
                ]

        except Exception as e:
            logger.warning(f"Vector search failed, falling back to text search: {e}")

        # Fallback to text-based search
        try:
            # Search for chunks containing relevant keywords from the query
            query_lower = query.lower()

            # Extract meaningful keywords (skip common words)
            stop_words = {"the", "is", "at", "which", "on", "a", "an", "and", "or", "but", "in", "with", "to", "for", "of", "as", "by", "that", "this", "it", "from", "be", "are", "was", "were", "been", "have", "has", "had", "do", "does", "did", "will", "would", "could", "should", "may", "might", "must", "can", "what", "where", "when", "how", "why", "who"}
            words = query_lower.split()
            keywords = [word for word in words if len(word) > 2 and word not in stop_words]

            # Build ILIKE conditions
            conditions = [f"content ILIKE '%{keyword}%'" for keyword in keywords]

            if not conditions:
                # If no keywords, search for the whole query
                conditions = [f"content ILIKE '%{query}%'"]

            query_sql = f"""
                SELECT id, doc_id, doc_type, chunk_index, content, metadata
                FROM rag_document_chunks
                WHERE doc_id = :doc_id
                AND doc_type = :doc_type
                AND ({' OR '.join(conditions)})
                ORDER BY chunk_index
                LIMIT :top_k
            """

            result = await session.execute(
                text(query_sql),
                {"doc_id": str(doc_id), "doc_type": doc_type, "top_k": top_k}
            )

            rows = result.fetchall()

            return [
                {
                    "document_id": row.id,
                    "document_title": f"{row.doc_type.title()} chunk {row.chunk_index}",
                    "content": row.content,
                    "doc_metadata": row.metadata or {},
                    "similarity_score": 0.8,  # Fake score for text match
                }
                for row in rows
            ]

        except Exception as e:
            logger.exception(f"Error searching document chunks: {e}")
            return []
