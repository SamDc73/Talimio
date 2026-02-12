-- Remove unused OAuth access token persistence column.

ALTER TABLE oauth_accounts
DROP COLUMN IF EXISTS access_token;
