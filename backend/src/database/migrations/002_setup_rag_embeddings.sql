-- Migration: Setup RAG embeddings infrastructure
-- Date: 2025-01-05
-- Description: Create pgvector extension and prepare for txtai embeddings

-- 1. Create pgvector extension if not exists
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Drop old problematic table if we own it (txtai will recreate properly)
DO $$ 
BEGIN
    -- Check if table exists and we can drop it
    IF EXISTS (
        SELECT 1 FROM pg_tables 
        WHERE schemaname = 'public' 
        AND tablename = 'txtai_embeddings'
    ) THEN
        -- Try to drop the table, ignore errors if we don't own it
        BEGIN
            DROP TABLE IF EXISTS txtai_embeddings CASCADE;
            RAISE NOTICE 'Dropped old txtai_embeddings table';
        EXCEPTION
            WHEN insufficient_privilege THEN
                RAISE NOTICE 'Cannot drop txtai_embeddings - insufficient privileges';
            WHEN OTHERS THEN
                RAISE NOTICE 'Error dropping txtai_embeddings: %', SQLERRM;
        END;
    END IF;
END $$;

-- 3. Create the course_document_embeddings table structure for txtai
-- This matches what txtai expects for pgvector backend
CREATE TABLE IF NOT EXISTS course_document_embeddings (
    -- Primary key
    id TEXT PRIMARY KEY,
    
    -- Vector embedding column (dimension will be set on first insert)
    embedding vector,
    
    -- Content and metadata stored as JSONB
    data JSONB,
    
    -- Tags for filtering (used by txtai for efficient searches)
    tags TEXT,
    
    -- Timestamp
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Index for vector similarity search will be created by txtai
    -- Additional indexes
    CONSTRAINT course_document_embeddings_id_check CHECK (id != '')
);

-- 4. Create indexes for better performance
-- Index on tags for filtering
CREATE INDEX IF NOT EXISTS idx_course_document_embeddings_tags 
ON course_document_embeddings USING btree(tags);

-- Index on JSONB data for metadata queries
CREATE INDEX IF NOT EXISTS idx_course_document_embeddings_data 
ON course_document_embeddings USING gin(data);

-- Index on created_at for time-based queries
CREATE INDEX IF NOT EXISTS idx_course_document_embeddings_created 
ON course_document_embeddings(created_at DESC);

-- 5. Grant necessary permissions (adjust user as needed)
-- Note: This assumes the application user needs full access
DO $$
BEGIN
    -- Grant permissions to authenticated users (Supabase pattern)
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
        GRANT ALL ON course_document_embeddings TO authenticated;
    END IF;
    
    -- Grant permissions to anon users for read access (if needed)
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
        GRANT SELECT ON course_document_embeddings TO anon;
    END IF;
EXCEPTION
    WHEN OTHERS THEN
        RAISE NOTICE 'Could not grant permissions: %', SQLERRM;
END $$;

-- 6. Create a helper function to clean up old embeddings
CREATE OR REPLACE FUNCTION cleanup_old_embeddings(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM course_document_embeddings
    WHERE created_at < CURRENT_TIMESTAMP - (days_to_keep || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 7. Add comment documentation
COMMENT ON TABLE course_document_embeddings IS 'Stores document embeddings for RAG (Retrieval Augmented Generation) using txtai with pgvector backend';
COMMENT ON COLUMN course_document_embeddings.id IS 'Unique identifier for each chunk (format: docUUID_chunkIndex)';
COMMENT ON COLUMN course_document_embeddings.embedding IS 'Vector embedding of the text chunk';
COMMENT ON COLUMN course_document_embeddings.data IS 'JSON data containing text content and metadata';
COMMENT ON COLUMN course_document_embeddings.tags IS 'Space-separated tags for efficient filtering (e.g., course:uuid type:pdf)';
COMMENT ON FUNCTION cleanup_old_embeddings IS 'Removes embeddings older than specified days (default 30)';

-- 8. Verify the setup
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully!';
    RAISE NOTICE 'pgvector extension: %', 
        (SELECT extversion FROM pg_extension WHERE extname = 'vector');
    RAISE NOTICE 'Table course_document_embeddings: %',
        CASE WHEN EXISTS (
            SELECT 1 FROM pg_tables 
            WHERE schemaname = 'public' 
            AND tablename = 'course_document_embeddings'
        ) THEN 'Created' ELSE 'Not created' END;
END $$;