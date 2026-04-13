ALTER TABLE lessons
DROP CONSTRAINT IF EXISTS lessons_course_id_concept_id_fkey;

ALTER TABLE lessons
ADD CONSTRAINT lessons_course_id_concept_id_fkey
FOREIGN KEY (course_id, concept_id)
REFERENCES course_concepts(course_id, concept_id)
ON DELETE CASCADE;
