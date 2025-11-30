CREATE TABLE IF NOT EXISTS user_mcp_servers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    auth_type TEXT NOT NULL DEFAULT 'none',
    auth_token TEXT,
    static_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS user_mcp_servers_user_name_idx
    ON user_mcp_servers (user_id, name);

CREATE INDEX IF NOT EXISTS user_mcp_servers_user_idx
    ON user_mcp_servers (user_id);
