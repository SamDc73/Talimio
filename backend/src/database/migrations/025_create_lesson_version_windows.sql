CREATE TABLE IF NOT EXISTS lesson_version_windows (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lesson_version_id UUID NOT NULL REFERENCES lesson_versions(id) ON DELETE CASCADE,
    window_index INTEGER NOT NULL,
    title VARCHAR(255),
    content TEXT NOT NULL,
    estimated_minutes INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_lesson_version_window_index UNIQUE (lesson_version_id, window_index)
)
