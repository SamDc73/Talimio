-- Remove legacy login backoff state table and align auth cleanup function.

DROP TABLE IF EXISTS auth_login_backoff_states;

DROP FUNCTION IF EXISTS cleanup_auth_operational_tables();

CREATE OR REPLACE FUNCTION cleanup_auth_operational_tables()
RETURNS TABLE (
    deleted_auth_sessions INTEGER,
    deleted_password_reset_token_uses INTEGER
)
LANGUAGE plpgsql
AS $function$
DECLARE
    current_time TIMESTAMPTZ := NOW();
BEGIN
    DELETE FROM auth_sessions
    WHERE expires_at < current_time
       OR (revoked_at IS NOT NULL AND revoked_at < current_time);
    GET DIAGNOSTICS deleted_auth_sessions = ROW_COUNT;

    DELETE FROM password_reset_token_uses
    WHERE expires_at < current_time;
    GET DIAGNOSTICS deleted_password_reset_token_uses = ROW_COUNT;

    RETURN NEXT;
END;
$function$;
