INSERT INTO lesson_versions (id, lesson_id, major_version, minor_version, version_kind, content, generation_metadata, created_at)
SELECT gen_random_uuid(), lessons.id, 1, 0, 'first_pass', lessons.content, '{}'::jsonb, COALESCE(lessons.updated_at, lessons.created_at, NOW())
FROM lessons
WHERE NOT EXISTS (
    SELECT 1
    FROM lesson_versions
    WHERE lesson_versions.lesson_id = lessons.id
)
