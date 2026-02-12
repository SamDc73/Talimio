-- Enforce non-null email addresses to match auth requirements.

ALTER TABLE users
ALTER COLUMN email SET NOT NULL;
