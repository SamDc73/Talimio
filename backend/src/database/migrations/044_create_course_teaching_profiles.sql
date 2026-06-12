-- Course-level teaching preferences (pedagogical canonical state).
-- Two rows max per course: explicit learner-stated settings and inferred
-- critique-derived conclusions stay separate; merge happens at read time.

CREATE TABLE IF NOT EXISTS course_teaching_profiles (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    source TEXT NOT NULL CHECK (source IN ('explicit', 'inferred')),
    pace_preference TEXT,
    example_style TEXT,
    quiz_density_preference TEXT,
    visual_preference TEXT,
    video_preference TEXT,
    tone_preference TEXT,
    avoid_list TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT course_teaching_profiles_course_id_source_key UNIQUE (course_id, source)
);

CREATE INDEX IF NOT EXISTS course_teaching_profiles_course_id_idx
    ON course_teaching_profiles (course_id);
