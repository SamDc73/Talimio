-- Chat becomes a pedagogical evidence source: course-scoped teaching
-- preferences stated to the assistant land as 'preference_stated' teaching
-- events (high-signal, consolidated immediately).

ALTER TABLE teaching_events DROP CONSTRAINT IF EXISTS teaching_events_event_type_check;
ALTER TABLE teaching_events DROP CONSTRAINT IF EXISTS teaching_events_event_type_allowed_check;
ALTER TABLE teaching_events ADD CONSTRAINT teaching_events_event_type_check
    CHECK (event_type IN ('lesson_version_shown', 'check_answered', 'lesson_regenerated',
                          'lesson_completed', 'delayed_outcome', 'preference_stated'));
