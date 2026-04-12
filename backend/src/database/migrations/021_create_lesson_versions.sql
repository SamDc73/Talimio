CREATE TABLE IF NOT EXISTS lesson_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    major_version INTEGER NOT NULL DEFAULT 1,
    minor_version INTEGER NOT NULL DEFAULT 0,
    version_kind VARCHAR(50) NOT NULL DEFAULT 'first_pass',
    content TEXT NOT NULL,
    generation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lesson_version_number UNIQUE (lesson_id, major_version, minor_version)
)
