ALTER TABLE courses
ADD COLUMN IF NOT EXISTS generation_status VARCHAR(20) NOT NULL DEFAULT 'ready';

ALTER TABLE courses
ADD CONSTRAINT courses_generation_status_check
CHECK (generation_status IN ('generating', 'ready', 'failed'));
