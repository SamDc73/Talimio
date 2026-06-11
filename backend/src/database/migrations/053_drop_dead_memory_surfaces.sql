-- Dead memory surfaces: enum values nothing writes and a column whose lane is
-- gone. 'legacy_migration' was never written (the mem0 store was empty at
-- cutover), shadow mode never ran, the apply path records only set/clear/defer,
-- and the per-lesson scope checkbox behind apply_across_course was retired —
-- old boolean values carry nothing the critique text doesn't.

ALTER TABLE user_profile_slots DROP CONSTRAINT IF EXISTS user_profile_slots_source_check;
ALTER TABLE user_profile_slots ADD CONSTRAINT user_profile_slots_source_check
    CHECK (source IN ('manual', 'inferred'));

ALTER TABLE user_profile_slot_events DROP CONSTRAINT IF EXISTS user_profile_slot_events_op_check;
ALTER TABLE user_profile_slot_events ADD CONSTRAINT user_profile_slot_events_op_check
    CHECK (op IN ('set', 'clear', 'defer'));

ALTER TABLE user_profile_slot_events DROP CONSTRAINT IF EXISTS user_profile_slot_events_status_check;
ALTER TABLE user_profile_slot_events ADD CONSTRAINT user_profile_slot_events_status_check
    CHECK (status IN ('applied', 'noop', 'rejected_stale', 'rejected_manual'));

ALTER TABLE lesson_feedback_events DROP COLUMN IF EXISTS apply_across_course;
