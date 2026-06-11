-- Authored evidence lives in one table. Chat-stated course preferences are
-- critiques without a lesson, so lesson_id becomes nullable and the
-- 'preference_stated' teaching-event type (wrong table for authored evidence)
-- is removed. The consolidation trigger rule becomes "which table got the
-- row": feedback events defer immediately, teaching events are threshold/nightly.

ALTER TABLE lesson_feedback_events ALTER COLUMN lesson_id DROP NOT NULL;

-- Carry any already-recorded stated preferences over to the authored table
-- before tightening the CHECK (the type shipped hours before this migration).
INSERT INTO lesson_feedback_events (course_id, critique_text)
SELECT course_id, COALESCE(NULLIF(details->>'quote', ''), details->>'preference', '[redacted]')
FROM teaching_events
WHERE event_type = 'preference_stated';

DELETE FROM teaching_events WHERE event_type = 'preference_stated';

ALTER TABLE teaching_events DROP CONSTRAINT IF EXISTS teaching_events_event_type_check;
ALTER TABLE teaching_events ADD CONSTRAINT teaching_events_event_type_check
    CHECK (event_type IN ('lesson_version_shown', 'check_answered', 'lesson_regenerated',
                          'lesson_completed', 'delayed_outcome'));
