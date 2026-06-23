-- Highlights now cover three concrete content types: book, video, and lesson.
-- The legacy constraint allowed 'course', but course outlines are never highlighted;
-- the only real course-scoped highlights are lesson bodies. Drop 'course', remap any
-- lesson-body rows stored as 'course' into 'lesson', delete the rest as outline junk,
-- and strip the internal _validation_type marker that validation used to inject.

-- 002_schema.sql created the column with an inline, auto-named check
-- (highlights_content_type_check); drop that and any later named variant.
ALTER TABLE highlights DROP CONSTRAINT IF EXISTS highlights_content_type_check;
ALTER TABLE highlights DROP CONSTRAINT IF EXISTS valid_content_type;

UPDATE highlights
SET content_type = 'lesson'
WHERE content_type = 'course'
  AND content_id IN (SELECT id FROM lessons);

DELETE FROM highlights
WHERE content_type = 'course';

UPDATE highlights
SET highlight_data = highlight_data - '_validation_type'
WHERE highlight_data ? '_validation_type';

ALTER TABLE highlights
ADD CONSTRAINT valid_content_type CHECK (content_type IN ('book', 'video', 'lesson'));
