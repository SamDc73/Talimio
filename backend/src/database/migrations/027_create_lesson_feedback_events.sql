CREATE TABLE IF NOT EXISTS lesson_feedback_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    lesson_version_id UUID REFERENCES lesson_versions(id) ON DELETE SET NULL,
    critique_text TEXT NOT NULL,
    apply_across_course BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
)
