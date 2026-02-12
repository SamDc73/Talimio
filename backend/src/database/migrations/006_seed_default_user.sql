-- Seed default user for single-user mode (AUTH_PROVIDER=none)
-- This user is required for development/testing when not using local auth
-- Note: The default user is harmless in multi-user mode (just unused)

-- Ensure column defaults exist (idempotent - safe for fresh DBs and existing ones)
ALTER TABLE users ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE;

ALTER TABLE user_mcp_servers ALTER COLUMN id SET DEFAULT gen_random_uuid();
ALTER TABLE user_mcp_servers ALTER COLUMN auth_type SET DEFAULT 'none';
ALTER TABLE user_mcp_servers ALTER COLUMN static_headers SET DEFAULT '{}'::jsonb;
ALTER TABLE user_mcp_servers ALTER COLUMN enabled SET DEFAULT TRUE;

-- Seed the default user for single-user mode
INSERT INTO users (id, username, email, password_hash, is_active)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'default_user',
    'default@localhost',
    'not_used_in_single_user_mode',
    TRUE
)
ON CONFLICT (id) DO NOTHING;
