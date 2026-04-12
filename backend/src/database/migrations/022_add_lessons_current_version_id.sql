ALTER TABLE lessons ADD COLUMN IF NOT EXISTS current_version_id UUID REFERENCES lesson_versions(id) ON DELETE SET NULL
