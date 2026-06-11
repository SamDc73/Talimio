ALTER TABLE lesson_versions
ADD COLUMN IF NOT EXISTS generation_status VARCHAR(20) NOT NULL DEFAULT 'ready';

ALTER TABLE lesson_versions
ADD COLUMN IF NOT EXISTS generation_error TEXT;

ALTER TABLE lesson_versions
ADD CONSTRAINT lesson_versions_generation_status_check
CHECK (generation_status IN ('generating', 'ready', 'failed'));
