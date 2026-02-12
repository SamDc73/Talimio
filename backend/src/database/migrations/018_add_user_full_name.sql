-- Add optional full-name field for account signup/profile display.

ALTER TABLE users
ADD COLUMN IF NOT EXISTS full_name VARCHAR(160);
