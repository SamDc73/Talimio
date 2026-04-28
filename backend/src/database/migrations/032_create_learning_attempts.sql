-- server-owned practice questions and idempotent learner attempts

CREATE TABLE IF NOT EXISTS learning_questions (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    lesson_id UUID NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    answer_kind VARCHAR(40) NOT NULL,
    hints JSONB NOT NULL DEFAULT '[]'::jsonb,
    structure_signature TEXT NOT NULL,
    predicted_p_correct DOUBLE PRECISION NOT NULL,
    target_probability DOUBLE PRECISION NOT NULL,
    target_low DOUBLE PRECISION NOT NULL,
    target_high DOUBLE PRECISION NOT NULL,
    core_model TEXT NOT NULL,
    practice_context VARCHAR(40) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT learning_questions_status_check CHECK (status IN ('active', 'answered', 'expired'))
);

CREATE INDEX IF NOT EXISTS learning_questions_user_course_concept_idx
    ON learning_questions (user_id, course_id, concept_id, created_at);

CREATE TABLE IF NOT EXISTS learning_attempts (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    attempt_id UUID NOT NULL,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES learning_questions(id) ON DELETE CASCADE,
    learner_answer TEXT NOT NULL,
    hints_used INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    is_correct BOOLEAN NOT NULL,
    grade_status VARCHAR(40) NOT NULL,
    feedback_markdown TEXT NOT NULL,
    mastery DOUBLE PRECISION NOT NULL,
    exposures INTEGER NOT NULL,
    next_review_at TIMESTAMPTZ NULL,
    response_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_learning_attempt_user_attempt UNIQUE (user_id, attempt_id)
);

CREATE INDEX IF NOT EXISTS learning_attempts_question_idx
    ON learning_attempts (question_id);
