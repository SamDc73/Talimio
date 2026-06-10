-- Typed facets on raw lesson critique events (evidence tier).
-- The raw critique_text stays canonical; facets are compact signals the
-- pedagogical updater extracts for aggregation. Scope intent already lives in
-- apply_across_course. facets_extracted_at doubles as the updater watermark.

ALTER TABLE lesson_feedback_events
    ADD COLUMN IF NOT EXISTS pace_signal TEXT,
    ADD COLUMN IF NOT EXISTS modality_signal TEXT,
    ADD COLUMN IF NOT EXISTS example_style_signal TEXT,
    ADD COLUMN IF NOT EXISTS quiz_density_signal TEXT,
    ADD COLUMN IF NOT EXISTS tone_signal TEXT,
    ADD COLUMN IF NOT EXISTS strategy_request_signal TEXT,
    ADD COLUMN IF NOT EXISTS facets_extracted_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS lesson_feedback_events_course_id_created_at_idx
    ON lesson_feedback_events (course_id, created_at);
