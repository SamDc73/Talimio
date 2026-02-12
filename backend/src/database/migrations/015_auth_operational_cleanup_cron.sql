-- Add DB-side auth cleanup lifecycle with optional pg_cron scheduling.

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

DO $block$
DECLARE
    cron_extension_installed BOOLEAN;
    existing_job_id BIGINT;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM pg_extension
        WHERE extname = 'pg_cron'
    )
    INTO cron_extension_installed;

    IF NOT cron_extension_installed THEN
        RETURN;
    END IF;

    EXECUTE $sql$
        SELECT jobid
        FROM cron.job
        WHERE jobname = 'auth_operational_cleanup'
        LIMIT 1
    $sql$
    INTO existing_job_id;

    IF existing_job_id IS NOT NULL THEN
        EXECUTE format('SELECT cron.unschedule(%s)', existing_job_id);
    END IF;

    EXECUTE $sql$
        SELECT cron.schedule(
            'auth_operational_cleanup',
            '15 * * * *',
            $$SELECT cleanup_auth_operational_tables();$$
        )
    $sql$;
END;
$block$;
