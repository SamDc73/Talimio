-- hidden assistant chat probe state for generated concept practice

CREATE TABLE IF NOT EXISTS assistant_active_probes (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    user_id UUID NOT NULL,
    conversation_id UUID NULL REFERENCES assistant_conversations(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    concept_id UUID NOT NULL REFERENCES concepts(id) ON DELETE CASCADE,
    lesson_id UUID NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
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
    practice_context VARCHAR(40) NOT NULL DEFAULT 'chat',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    answered_correct BOOLEAN NULL,
    answer_attempts INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT assistant_active_probes_status_check CHECK (status IN ('active', 'answered', 'expired'))
);

CREATE INDEX IF NOT EXISTS assistant_active_probes_user_thread_idx
    ON assistant_active_probes (user_id, conversation_id, status);
CREATE INDEX IF NOT EXISTS assistant_active_probes_user_concept_idx
    ON assistant_active_probes (user_id, course_id, concept_id, created_at DESC);
CREATE UNIQUE INDEX IF NOT EXISTS assistant_active_probes_one_active_per_thread_concept_idx
    ON assistant_active_probes (user_id, conversation_id, course_id, concept_id)
    WHERE status = 'active' AND conversation_id IS NOT NULL;
