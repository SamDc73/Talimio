-- base schema
-- Base schema (core, tagging, progress, concepts, RAG, mem0)

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(100) NOT NULL UNIQUE,
    email VARCHAR(255) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_preferences (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    preferences JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS courses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    tags TEXT,
    setup_commands TEXT,
    adaptive_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lessons (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    content TEXT NOT NULL,
    "order" INTEGER NOT NULL DEFAULT 0,
    module_name VARCHAR(255),
    module_order INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS course_documents (
    id SERIAL PRIMARY KEY,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    document_type VARCHAR(50),
    title VARCHAR(255) NOT NULL,
    file_path VARCHAR(500),
    source_url VARCHAR(500),
    crawl_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ,
    embedded_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending'
);

CREATE TABLE IF NOT EXISTS books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title VARCHAR(500) NOT NULL,
    subtitle VARCHAR(500),
    author VARCHAR(200) NOT NULL,
    description TEXT,
    isbn VARCHAR(20),
    file_path VARCHAR(1000) NOT NULL,
    file_type VARCHAR(10) NOT NULL,
    file_size INTEGER NOT NULL,
    total_pages INTEGER,
    language VARCHAR(50),
    publication_year INTEGER,
    publisher VARCHAR(200),
    tags TEXT,
    table_of_contents TEXT,
    file_hash VARCHAR(64),
    rag_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    rag_processed_at TIMESTAMPTZ,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (file_hash)
);

CREATE TABLE IF NOT EXISTS videos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    youtube_id VARCHAR(20) NOT NULL UNIQUE,
    url VARCHAR(255) NOT NULL,
    title VARCHAR(500) NOT NULL,
    channel VARCHAR(255) NOT NULL,
    channel_id VARCHAR(50) NOT NULL,
    duration INTEGER NOT NULL,
    thumbnail_url VARCHAR(500),
    description TEXT,
    tags TEXT,
    transcript TEXT,
    transcript_data JSONB,
    transcript_url VARCHAR(500),
    rag_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    rag_processed_at TIMESTAMPTZ,
    chapters_status VARCHAR(50) NOT NULL DEFAULT 'pending',
    chapters_extracted_at TIMESTAMPTZ,
    archived BOOLEAN NOT NULL DEFAULT FALSE,
    archived_at TIMESTAMPTZ,
    published_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS video_chapters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_id UUID NOT NULL REFERENCES videos(id) ON DELETE CASCADE,
    chapter_number INTEGER NOT NULL,
    title VARCHAR(500) NOT NULL,
    start_time INTEGER,
    end_time INTEGER,
    status VARCHAR(50) NOT NULL DEFAULT 'not_started',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS highlights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('book', 'course', 'video')),
    content_id UUID NOT NULL,
    highlight_data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(50),
    color VARCHAR(7),
    usage_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tag_associations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tag_id UUID NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
    content_id UUID NOT NULL,
    content_type VARCHAR(20) NOT NULL,
    user_id UUID NOT NULL,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    auto_generated BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    content_id UUID NOT NULL,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('course', 'book', 'video')),
    progress_percentage DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (progress_percentage >= 0 AND progress_percentage <= 100),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, content_id)
);

CREATE TABLE IF NOT EXISTS ai_custom_instructions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    instructions TEXT NOT NULL,
    context VARCHAR(100) NOT NULL DEFAULT 'global',
    context_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, context, context_id)
);

CREATE TABLE IF NOT EXISTS learning_memories (
    id UUID PRIMARY KEY,
    vector VECTOR(${MEMORY_EMBEDDING_OUTPUT_DIM}),
    payload JSONB
);

CREATE TABLE IF NOT EXISTS mem0migrations (
    id UUID PRIMARY KEY,
    vector VECTOR(${MEMORY_EMBEDDING_OUTPUT_DIM}),
    payload JSONB
);

CREATE TABLE IF NOT EXISTS rag_document_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id UUID NOT NULL,
    doc_type TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(${RAG_EMBEDDING_OUTPUT_DIM}),
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concepts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    domain TEXT,
    slug TEXT UNIQUE,
    name TEXT,
    description TEXT,
    difficulty SMALLINT,
    embedding VECTOR(${RAG_EMBEDDING_OUTPUT_DIM}),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS concept_prerequisites (
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    prereq_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    PRIMARY KEY (concept_id, prereq_id)
);

CREATE TABLE IF NOT EXISTS course_concepts (
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    order_hint INTEGER,
    PRIMARY KEY (course_id, concept_id)
);

CREATE TABLE IF NOT EXISTS user_concept_state (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    last_seen_at TIMESTAMPTZ,
    s_mastery DOUBLE PRECISION DEFAULT 0,
        exposures INTEGER NOT NULL DEFAULT 0,
    next_review_at TIMESTAMPTZ,
        learner_profile JSONB NOT NULL DEFAULT '{"success_rate": 0.5, "learning_speed": 1.0, "retention_rate": 0.8, "semantic_sensitivity": 1.0}'::jsonb,
    PRIMARY KEY (user_id, concept_id)
);

CREATE TABLE IF NOT EXISTS probe_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    correct BOOLEAN,
    latency_ms INTEGER,
    context_tag TEXT,
    extra JSONB,
    ts TIMESTAMPTZ DEFAULT NOW(),
    rating SMALLINT,
    review_duration_ms INTEGER
);

CREATE TABLE IF NOT EXISTS concept_similarities (
    concept_a_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    concept_b_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    similarity DOUBLE PRECISION NOT NULL,
    computed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (concept_a_id, concept_b_id)
);
