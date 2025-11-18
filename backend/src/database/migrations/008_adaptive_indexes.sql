-- autocommit
-- 008_adaptive_indexes.sql
-- Performance indexes to support adaptive courses and scheduling

-- User concept state hot paths
CREATE INDEX IF NOT EXISTS user_concept_state_user_id_idx ON user_concept_state(user_id);
CREATE INDEX IF NOT EXISTS user_concept_state_next_review_at_idx ON user_concept_state(next_review_at);

-- Probe events timeline queries
CREATE INDEX IF NOT EXISTS probe_events_user_ts_idx ON probe_events(user_id, ts);
