"""Lightweight SQL migration runner for PostgreSQL session poolers."""

import logging
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.config import env
from src.config.settings import get_settings
from src.database.engine import engine as default_engine


logger = logging.getLogger(__name__)
_MIGRATION_LOCK_KEY = "schema_migrations"
_AUTOCOMMIT_TAG = "-- autocommit"
_DEFAULT_RAG_EMBEDDING_OUTPUT_DIM = 1024
_DEFAULT_MEMORY_EMBEDDING_OUTPUT_DIM = 1024


def _migrations_dir() -> Path:
    return Path(__file__).parent / "migrations"


def _is_autocommit(sql: str) -> bool:
    return sql.lstrip().lower().startswith(_AUTOCOMMIT_TAG)


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _interpolate_env(sql: str) -> str:
    """Replace known ${VAR} placeholders in SQL with env values."""

    def _resolve_int(name: str, default: int) -> int:
        raw_value = env(name)
        if raw_value in (None, ""):
            return default
        try:
            return int(raw_value)
        except (TypeError, ValueError):
            logger.warning("migration.placeholder.invalid", extra={"placeholder_name": name, "raw_value": raw_value, "default": default})
            return default

    rag_dim = _resolve_int("RAG_EMBEDDING_OUTPUT_DIM", _DEFAULT_RAG_EMBEDDING_OUTPUT_DIM)
    mem_dim = _resolve_int("MEMORY_EMBEDDING_OUTPUT_DIM", _DEFAULT_MEMORY_EMBEDDING_OUTPUT_DIM)

    return sql.replace("${RAG_EMBEDDING_OUTPUT_DIM}", str(rag_dim)).replace(
        "${MEMORY_EMBEDDING_OUTPUT_DIM}",
        str(mem_dim),
    )


def _sorted_sql_files(directory: Path) -> list[Path]:
    return sorted(file for file in directory.iterdir() if file.suffix == ".sql")


def _log_migration_check_skipped(*, reason: str, migrations_dir: Path | None = None) -> None:
    extra: dict[str, str] = {"reason": reason}
    if migrations_dir is not None:
        extra["migrations_dir"] = str(migrations_dir)
    logger.debug("migration.check.skipped", extra=extra)


async def _ensure_schema_table(conn: AsyncConnection) -> None:
    await conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
    )


async def _get_applied(conn: AsyncConnection) -> Iterable[str]:
    result = await conn.execute(text("SELECT filename FROM schema_migrations"))
    return (row[0] for row in result)


async def _acquire_lock(conn: AsyncConnection) -> bool:
    result = await conn.execute(
        text("SELECT pg_try_advisory_lock(hashtext(:lock_key))"),
        {"lock_key": _MIGRATION_LOCK_KEY},
    )
    return bool(result.scalar())


async def _release_lock(conn: AsyncConnection) -> None:
    await conn.execute(
        text("SELECT pg_advisory_unlock(hashtext(:lock_key))"),
        {"lock_key": _MIGRATION_LOCK_KEY},
    )


async def _execute_migration_sql(
    *,
    engine: AsyncEngine,
    conn: AsyncConnection,
    sql_content: str,
    autocommit: bool,
) -> None:
    if autocommit:
        async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as auto_conn:
            await auto_conn.exec_driver_sql(sql_content)
        return

    async with conn.begin():
        await conn.exec_driver_sql(sql_content)


async def _record_applied_migration(conn: AsyncConnection, *, filename: str) -> None:
    async with conn.begin():
        await conn.execute(
            text("INSERT INTO schema_migrations (filename) VALUES (:filename)"),
            {"filename": filename},
        )


async def _apply_pending_migrations(
    *,
    engine: AsyncEngine,
    conn: AsyncConnection,
    migration_files: list[Path],
    applied: set[str],
    verbose: bool,
) -> int:
    applied_count = 0
    for path in migration_files:
        if path.name in applied:
            continue

        sql_content = _interpolate_env(_read_sql(path))
        autocommit = _is_autocommit(sql_content)
        await _execute_migration_sql(engine=engine, conn=conn, sql_content=sql_content, autocommit=autocommit)
        await _record_applied_migration(conn, filename=path.name)
        applied_count += 1

        if verbose:
            logger.info("migration.applied", extra={"migration_filename": path.name, "autocommit": autocommit})

    return applied_count


async def apply_migrations(db_engine: AsyncEngine | None = None) -> int:
    """Apply pending SQL migrations in order and return the number applied."""
    engine = db_engine or default_engine

    settings = get_settings()
    if not settings.MIGRATIONS_AUTO_APPLY:
        _log_migration_check_skipped(reason="auto_apply_disabled")
        return 0

    migrations_dir = Path(settings.MIGRATIONS_DIR) if settings.MIGRATIONS_DIR else _migrations_dir()
    verbose = settings.MIGRATIONS_VERBOSE

    if not migrations_dir.exists():
        _log_migration_check_skipped(reason="directory_missing", migrations_dir=migrations_dir)
        return 0

    migration_files = _sorted_sql_files(migrations_dir)
    if not migration_files:
        _log_migration_check_skipped(reason="no_files", migrations_dir=migrations_dir)
        return 0

    async with engine.connect() as conn:
        await _ensure_schema_table(conn)
        await conn.commit()

    async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as lock_conn:
        locked = await _acquire_lock(lock_conn)
        if not locked:
            _log_migration_check_skipped(reason="lock_unavailable")
            return 0

        try:
            async with engine.connect() as conn:
                applied = set(await _get_applied(conn))
                await conn.rollback()
                return await _apply_pending_migrations(
                    engine=engine,
                    conn=conn,
                    migration_files=migration_files,
                    applied=applied,
                    verbose=verbose,
                )
        finally:
            await _release_lock(lock_conn)


async def main() -> None:
    """Run migrations when executed as a script."""
    _ = await apply_migrations()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
