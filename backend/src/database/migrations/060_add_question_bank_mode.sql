-- Question-bank courses: instructor-authored questions with no lessons.
-- courses.mode names where the learning material comes from; adaptive_enabled
-- stays the LECTOR switch and is true for both adaptive and question_bank.

ALTER TABLE courses
ADD COLUMN IF NOT EXISTS mode VARCHAR(20) NOT NULL DEFAULT 'standard';

UPDATE courses
SET mode = 'adaptive'
WHERE adaptive_enabled = TRUE
  AND mode = 'standard';

ALTER TABLE courses
ADD CONSTRAINT courses_mode_check
CHECK (mode IN ('standard', 'adaptive', 'question_bank'));

-- The bank is the course's canon and carries no learner state; per-learner
-- grading rows are materialized into learning_questions keyed by source_key.
-- concept_id is NULL until the outline job maps the question onto the graph.
CREATE TABLE IF NOT EXISTS course_questions (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    concept_id UUID NULL REFERENCES concepts(id) ON DELETE SET NULL,
    position INTEGER NOT NULL,
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    answer_kind VARCHAR(40) NOT NULL,
    choices JSONB NOT NULL DEFAULT '[]'::jsonb,
    hints JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT course_questions_course_id_position_key UNIQUE (course_id, position),
    CONSTRAINT course_questions_answer_kind_check CHECK (answer_kind IN ('text', 'latex', 'choice'))
);

CREATE INDEX IF NOT EXISTS course_questions_course_concept_idx
    ON course_questions (course_id, concept_id);

-- Bank rows have no lesson, so the inline partial index (which keys on lesson
-- columns) cannot dedupe them; one materialized row per learner and bank question.
CREATE UNIQUE INDEX IF NOT EXISTS learning_questions_question_bank_source_key_idx
    ON learning_questions (user_id, course_id, source_key)
    WHERE source_component = 'question_bank';
