-- assistant conversation threads + history persistence

CREATE OR REPLACE FUNCTION app_uuid7() RETURNS UUID AS $$
DECLARE
    generated UUID;
BEGIN
    IF to_regproc('uuidv7') IS NOT NULL THEN
        EXECUTE 'SELECT uuidv7()' INTO generated;
        RETURN generated;
    END IF;

    RETURN gen_random_uuid();
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS assistant_conversations (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    user_id UUID NOT NULL,
    title TEXT NULL,
    status TEXT NOT NULL DEFAULT 'regular',
    context_type TEXT NULL,
    context_id UUID NULL,
    context_meta JSONB NOT NULL DEFAULT '{}'::jsonb,
    head_message_id TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT assistant_conversations_status_check CHECK (status IN ('regular', 'archived')),
    CONSTRAINT assistant_conversations_context_type_check CHECK (context_type IN ('book', 'video', 'course'))
);

CREATE TABLE IF NOT EXISTS assistant_conversation_history_items (
    id UUID PRIMARY KEY DEFAULT app_uuid7(),
    conversation_id UUID NOT NULL REFERENCES assistant_conversations(id) ON DELETE CASCADE,
    seq BIGINT GENERATED ALWAYS AS IDENTITY,
    aui_message_id TEXT NOT NULL,
    parent_aui_message_id TEXT NULL,
    message_json JSONB NOT NULL,
    run_config JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL,
    inserted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT assistant_conv_hist_conv_id_msg_id_key UNIQUE (
        conversation_id,
        aui_message_id
    )
);

CREATE INDEX IF NOT EXISTS assistant_conversations_user_id_updated_at_idx
    ON assistant_conversations (user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS assistant_conv_hist_conv_id_seq_idx
    ON assistant_conversation_history_items (conversation_id, seq ASC);
CREATE INDEX IF NOT EXISTS assistant_conv_hist_conv_id_parent_msg_idx
    ON assistant_conversation_history_items (conversation_id, parent_aui_message_id);
