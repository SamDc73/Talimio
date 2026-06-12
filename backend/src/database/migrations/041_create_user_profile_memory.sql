-- Canonical durable user profile memory.
-- user_profile_slots: one active value per user+slot (canonical state tier).
-- user_profile_slot_events: provenance log for inferred writes (evidence tier);
-- evidence_text may be redacted on explicit user-forget, keeping a structural tombstone.

CREATE TABLE IF NOT EXISTS user_profile_slots (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slot TEXT NOT NULL,
    value TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('manual', 'inferred', 'legacy_migration')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_evidence_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS user_profile_slots_user_id_slot_active_key
    ON user_profile_slots (user_id, slot) WHERE is_active;

CREATE INDEX IF NOT EXISTS user_profile_slots_user_id_idx
    ON user_profile_slots (user_id);

CREATE TABLE IF NOT EXISTS user_profile_slot_events (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slot TEXT NOT NULL,
    op TEXT NOT NULL CHECK (op IN ('set', 'clear', 'ignore', 'defer')),
    proposed_value TEXT,
    confidence DOUBLE PRECISION CHECK (confidence >= 0 AND confidence <= 1),
    source TEXT NOT NULL,
    message_id TEXT,
    source_message_created_at TIMESTAMPTZ,
    evidence_text TEXT,
    status TEXT NOT NULL CHECK (status IN ('applied', 'noop', 'rejected_stale', 'rejected_manual', 'shadow')),
    redacted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_profile_slot_events_user_id_created_at_idx
    ON user_profile_slot_events (user_id, created_at);
