-- autocommit
-- hnsw indexes
-- HNSW indexes for vector search


-- Ensure vector columns have fixed dimensions required by HNSW
DO $$
BEGIN
  -- learning_memories.vector should be vector(${MEMORY_EMBEDDING_OUTPUT_DIM})
  BEGIN
    EXECUTE 'ALTER TABLE learning_memories
             ALTER COLUMN vector TYPE vector(${MEMORY_EMBEDDING_OUTPUT_DIM})
             USING vector';
  EXCEPTION WHEN others THEN
    -- Ignore if column already has dimensions or table doesn't exist yet
    NULL;
  END;

  -- rag_document_chunks.embedding should be vector(${RAG_EMBEDDING_OUTPUT_DIM})
  BEGIN
    EXECUTE 'ALTER TABLE rag_document_chunks
             ALTER COLUMN embedding TYPE vector(${RAG_EMBEDDING_OUTPUT_DIM})
             USING embedding';
  EXCEPTION WHEN others THEN
    NULL;
  END;

  -- concepts.embedding should be vector(${RAG_EMBEDDING_OUTPUT_DIM})
  BEGIN
    EXECUTE 'ALTER TABLE concepts
             ALTER COLUMN embedding TYPE vector(${RAG_EMBEDDING_OUTPUT_DIM})
             USING embedding';
  EXCEPTION WHEN others THEN
    NULL;
  END;
END $$;

-- Create HNSW indexes (idempotent); tolerate environments where columns can't be altered
DO $$
BEGIN
  BEGIN
    EXECUTE 'CREATE INDEX IF NOT EXISTS lm_vec_cos ON learning_memories USING hnsw (vector vector_cosine_ops)';
  EXCEPTION WHEN others THEN
    NULL;
  END;

  BEGIN
    EXECUTE 'CREATE INDEX IF NOT EXISTS rag_document_chunks_embedding_hnsw_idx ON rag_document_chunks USING hnsw (embedding vector_cosine_ops)';
  EXCEPTION WHEN others THEN
    NULL;
  END;
END $$;
