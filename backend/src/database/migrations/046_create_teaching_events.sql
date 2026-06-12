-- Pedagogical evidence tier: what was shown to the learner and how they responded.
-- One narrow typed core plus a details JSONB for media/density signals, so the
-- planner can compare outcomes across teaching choices without a column per knob.

CREATE TABLE IF NOT EXISTS teaching_events (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    lesson_id UUID,
    lesson_version_id UUID,
    concept_id UUID,
    event_type TEXT NOT NULL CHECK (event_type IN ('lesson_version_shown', 'check_answered', 'lesson_regenerated', 'lesson_completed', 'delayed_outcome')),
    strategy_label TEXT,
    window_count INTEGER,
    duration_ms INTEGER,
    hints_used INTEGER,
    outcome TEXT,
    details JSONB NOT NULL DEFAULT '{}',
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS teaching_events_user_id_course_id_occurred_at_idx
    ON teaching_events (user_id, course_id, occurred_at);
