CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

ALTER TABLE lessons
ADD COLUMN IF NOT EXISTS concept_id UUID;

DO $$
DECLARE
    ambiguous_count INTEGER;
    missing_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO ambiguous_count
    FROM (
        SELECT lessons.id
        FROM lessons
        JOIN courses ON courses.id = lessons.course_id
        JOIN course_concepts ON course_concepts.course_id = lessons.course_id
        WHERE courses.adaptive_enabled IS TRUE
          AND uuid_generate_v5(
              uuid_ns_url(),
              format('concept-lesson:%%s:%%s', lessons.course_id, course_concepts.concept_id)
          ) = lessons.id
        GROUP BY lessons.id
        HAVING COUNT(*) > 1
    ) AS ambiguous_lessons;

    IF ambiguous_count > 0 THEN
        RAISE EXCEPTION 'Adaptive lesson concept backfill found ambiguous matches for %% lesson rows', ambiguous_count;
    END IF;

    UPDATE lessons
    SET concept_id = mapped.concept_id
    FROM (
        SELECT lessons.id AS lesson_id, course_concepts.concept_id
        FROM lessons
        JOIN courses ON courses.id = lessons.course_id
        JOIN course_concepts ON course_concepts.course_id = lessons.course_id
        WHERE courses.adaptive_enabled IS TRUE
          AND uuid_generate_v5(
              uuid_ns_url(),
              format('concept-lesson:%%s:%%s', lessons.course_id, course_concepts.concept_id)
          ) = lessons.id
    ) AS mapped
    WHERE lessons.id = mapped.lesson_id
      AND lessons.concept_id IS NULL;

    SELECT COUNT(*) INTO missing_count
    FROM lessons
    JOIN courses ON courses.id = lessons.course_id
    WHERE courses.adaptive_enabled IS TRUE
      AND lessons.concept_id IS NULL;

    IF missing_count > 0 THEN
        RAISE EXCEPTION 'Adaptive lesson concept backfill left %% adaptive lessons without concept_id', missing_count;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'lessons_course_id_concept_id_fkey'
    ) THEN
        ALTER TABLE lessons
        ADD CONSTRAINT lessons_course_id_concept_id_fkey
        FOREIGN KEY (course_id, concept_id)
        REFERENCES course_concepts(course_id, concept_id);
    END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS lessons_course_id_concept_id_key
ON lessons (course_id, concept_id)
WHERE concept_id IS NOT NULL;
