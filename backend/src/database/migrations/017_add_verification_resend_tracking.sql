-- Track verification resend attempts directly on users for simple auth throttling.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS verification_email_last_sent_at TIMESTAMPTZ;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS verification_email_resend_attempts INTEGER NOT NULL DEFAULT 0;

ALTER TABLE users
ADD COLUMN IF NOT EXISTS verification_email_resend_window_started_at TIMESTAMPTZ;
