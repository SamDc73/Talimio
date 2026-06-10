-- Canonical pedagogical summary: one labeled plain-text block per user+course
-- (the storage shape frontier models are post-trained to edit), plus an
-- append-only full-text revision log as provenance and rebuild substrate.

CREATE TABLE IF NOT EXISTS student_cards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    card_text TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT student_cards_user_id_course_id_key UNIQUE (user_id, course_id)
);

CREATE TABLE IF NOT EXISTS student_card_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    card_id UUID NOT NULL REFERENCES student_cards(id) ON DELETE CASCADE,
    revision INTEGER NOT NULL,
    card_text TEXT NOT NULL,
    tool_call JSONB NOT NULL DEFAULT '{}',
    evidence_refs JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT student_card_revisions_card_id_revision_key UNIQUE (card_id, revision)
);

CREATE INDEX IF NOT EXISTS student_card_revisions_card_id_idx
    ON student_card_revisions (card_id);
