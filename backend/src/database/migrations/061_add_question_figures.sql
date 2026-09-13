-- Question figures: a static JSXGraph drawing stored as data (one board.create
-- call per element) so instructor questions carry diagrams without screenshots.
ALTER TABLE course_questions
ADD COLUMN IF NOT EXISTS figure JSONB NULL;
