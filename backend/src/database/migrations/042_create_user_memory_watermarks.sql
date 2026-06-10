-- Per-user processing watermark for the profile-memory maintenance pass.
-- Conversation history items carry a table-wide monotonic seq (IDENTITY), so
-- one BIGINT per user marks everything at or below it as already evaluated.

CREATE TABLE IF NOT EXISTS user_memory_watermarks (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_processed_seq BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
