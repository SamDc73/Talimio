UPDATE lessons
SET current_version_id = lesson_versions.id
FROM lesson_versions
WHERE lesson_versions.lesson_id = lessons.id
  AND lesson_versions.major_version = 1
  AND lesson_versions.minor_version = 0
  AND lessons.current_version_id IS NULL
