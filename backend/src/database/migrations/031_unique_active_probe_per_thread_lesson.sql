CREATE UNIQUE INDEX IF NOT EXISTS assistant_active_probes_one_active_per_thread_lesson_idx
ON assistant_active_probes (user_id, conversation_id, course_id, lesson_id)
WHERE status = 'active' AND conversation_id IS NOT NULL AND lesson_id IS NOT NULL;
