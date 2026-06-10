-- Explicit forget of pedagogical memory: immediate soft-delete; the async
-- cascade task redacts linked learner-authored evidence afterwards.

ALTER TABLE student_cards ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
