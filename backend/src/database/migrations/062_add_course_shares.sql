-- Share links: redeeming one forks the course's backbone (the row, its concept
-- links, and the bank) for the redeeming learner. Learner state never travels.
-- The table has no user_id on purpose: the course implies its owner.
CREATE TABLE IF NOT EXISTS course_shares (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    token TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT course_shares_token_key UNIQUE (token)
);

CREATE INDEX IF NOT EXISTS course_shares_course_id_idx
    ON course_shares (course_id);

-- Lineage: the course a fork was copied from. SET NULL so deleting the source
-- never breaks its copies, matching how concepts already outlive courses.
ALTER TABLE courses
ADD COLUMN IF NOT EXISTS forked_from_course_id UUID NULL REFERENCES courses(id) ON DELETE SET NULL;
