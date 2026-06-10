-- Pedagogical retrieval layer: distilled, per-learner teaching facts the
-- lesson-writer/assistant can search at generation time. Each note keeps a
-- short verbatim source excerpt because the lexical (full-text) leg ranks
-- raw learner phrasing far better than distilled summaries.

CREATE TABLE IF NOT EXISTS pedagogical_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_id UUID REFERENCES courses(id) ON DELETE CASCADE,
    -- Distilled fact, ~1-2 sentences.
    note TEXT NOT NULL,
    -- One-line when/how it was learned, with an absolute date.
    scene_trace TEXT NOT NULL,
    -- Short source excerpt; feeds the lexical leg (distilled text degrades BM25-style ranking).
    verbatim_quote TEXT NOT NULL DEFAULT '',
    source_kind TEXT NOT NULL CHECK (source_kind IN ('lesson_feedback_event', 'teaching_event', 'updater_reflection')),
    source_id UUID,
    occurred_at TIMESTAMPTZ NOT NULL,
    embedding VECTOR(${RAG_EMBEDDING_OUTPUT_DIM}),
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pedagogical_notes_user_id_idx
    ON pedagogical_notes (user_id);
CREATE INDEX IF NOT EXISTS pedagogical_notes_user_id_course_id_idx
    ON pedagogical_notes (user_id, course_id);

-- Deliberately NO ANN index on embedding: per-user corpora are hundreds of
-- rows, so the exact ORDER BY embedding <=> $1 scan is perfect-recall and
-- cheap; an HNSW index would only add build cost and approximate recall.
