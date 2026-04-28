ALTER TABLE learning_questions
    ADD COLUMN IF NOT EXISTS grade_kind VARCHAR(40) NOT NULL DEFAULT 'practice_answer',
    ADD COLUMN IF NOT EXISTS expected_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS question_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS source_component VARCHAR(80) NULL,
    ADD COLUMN IF NOT EXISTS source_key TEXT NULL,
    ADD COLUMN IF NOT EXISTS lesson_version_id UUID NULL REFERENCES lesson_versions(id) ON DELETE CASCADE;

ALTER TABLE learning_questions
    ALTER COLUMN expected_answer DROP NOT NULL,
    ALTER COLUMN answer_kind DROP NOT NULL;

ALTER TABLE learning_attempts
    ADD COLUMN IF NOT EXISTS answer_payload JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE UNIQUE INDEX IF NOT EXISTS learning_questions_inline_source_key_idx
    ON learning_questions (user_id, course_id, lesson_id, lesson_version_id, source_key)
    WHERE source_key IS NOT NULL;
