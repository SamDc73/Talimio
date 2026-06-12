-- Migrations 041/044/046/047/050 originally created these tables with
-- gen_random_uuid() id defaults and were later edited in place to app_uuid7().
-- The runner tracks applied migrations by filename, so databases that already
-- ran them still carry the uuid4 default. Align existing databases with the
-- edited CREATE statements and the ORM server_default.

ALTER TABLE user_profile_slots ALTER COLUMN id SET DEFAULT app_uuid7();

ALTER TABLE user_profile_slot_events ALTER COLUMN id SET DEFAULT app_uuid7();

ALTER TABLE course_teaching_profiles ALTER COLUMN id SET DEFAULT app_uuid7();

ALTER TABLE teaching_events ALTER COLUMN id SET DEFAULT app_uuid7();

ALTER TABLE student_cards ALTER COLUMN id SET DEFAULT app_uuid7();

ALTER TABLE student_card_revisions ALTER COLUMN id SET DEFAULT app_uuid7();

ALTER TABLE pedagogical_notes ALTER COLUMN id SET DEFAULT app_uuid7();
