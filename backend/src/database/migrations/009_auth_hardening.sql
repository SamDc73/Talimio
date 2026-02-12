-- Local auth hardening: token versioning + one-time password reset tokens (idempotent)

ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_token_version INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS password_reset_token_uses (
    jti VARCHAR(128) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_password_reset_token_uses_user_id ON password_reset_token_uses(user_id);
CREATE INDEX IF NOT EXISTS ix_password_reset_token_uses_expires_at ON password_reset_token_uses(expires_at);
