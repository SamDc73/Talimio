-- extensions.sql
-- Ensure required extensions exist BEFORE any schema uses them.
-- This lets a brand-new database initialize without manual steps.

-- UUID generation used by DEFAULT gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- pgvector for VECTOR(...) columns and <=> operator
-- If pgvector isn't installed on the server, surface a clear error
-- instead of failing later when creating tables.
DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION
  WHEN undefined_file THEN
    RAISE EXCEPTION 'pgvector extension is not installed on this PostgreSQL server.\n'
                    'Install pgvector or use a Postgres offering with pgvector enabled.\n'
                    'Docs: https://github.com/pgvector/pgvector';
END $$;

-- trigram text search (used by LIKE/ILIKE acceleration, optional but harmless)
CREATE EXTENSION IF NOT EXISTS pg_trgm;
