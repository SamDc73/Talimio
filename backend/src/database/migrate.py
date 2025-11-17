"""Lightweight SQL migration runner for Supabase session pooler."""

import logging
import os
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.database.engine import engine as default_engine


logger = logging.getLogger(__name__)
_MIGRATION_LOCK_KEY = "schema_migrations"
_AUTOCOMMIT_TAG = "-- autocommit"
_BOOL_TRUE = {"1", "true", "yes", "on"}


def _env_flag(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw is None:
        return default
    return raw.strip().lower() in _BOOL_TRUE


def _migrations_dir() -> Path:
    return Path(__file__).parent / "migrations"


def _is_autocommit(sql: str) -> bool:
    return sql.lstrip().lower().startswith(_AUTOCOMMIT_TAG)


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _sorted_sql_files(directory: Path) -> list[Path]:
    return sorted(file for file in directory.iterdir() if file.suffix == ".sql")


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


async def apply_migrations(db_engine: AsyncEngine | None = None) -> None:
    """Apply pending SQL migrations in order.

    Respects MIGRATIONS_AUTO_APPLY (default true), MIGRATIONS_DIR, and MIGRATIONS_VERBOSE.
    Files starting with "-- autocommit" run in AUTOCOMMIT mode (needed for CONCURRENTLY indexes).
    """
    engine = db_engine or default_engine

    if not _env_flag(key="MIGRATIONS_AUTO_APPLY", default=True):
        logger.info("Migrations auto-apply disabled; skipping")
        return

    migrations_dir = Path(os.getenv("MIGRATIONS_DIR") or _migrations_dir())
    verbose = _env_flag(key="MIGRATIONS_VERBOSE", default=False)

    if not migrations_dir.exists():
        logger.warning("Migrations directory %s does not exist; skipping", migrations_dir)
        return

    migration_files = _sorted_sql_files(migrations_dir)
    if not migration_files:
        logger.info("No migration files found in %s", migrations_dir)
        return

    # 1) Ensure schema_migrations exists in a dedicated transaction
    async with engine.connect() as conn:
        await _ensure_schema_table(conn)
        await conn.commit()

    # 2) Acquire advisory lock using an autocommit connection
    async with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as lock_conn:
        locked = await _acquire_lock(lock_conn)
        if not locked:
            logger.info("Another migration process is running; skipping")
            return

        try:
            # 3) Use a fresh connection for applying migrations
            async with engine.connect() as conn:
                applied = set(await _get_applied(conn))
                await conn.rollback()

                for path in migration_files:
                    if path.name in applied:
                        continue

                    sql_content = _read_sql(path)
                    autocommit = _is_autocommit(sql_content)

                    if autocommit:
                        async with engine.execution_options(
                            isolation_level="AUTOCOMMIT"
                        ).connect() as auto_conn:
                            await auto_conn.exec_driver_sql(sql_content)
                    else:
                        async with conn.begin():
                            await conn.exec_driver_sql(sql_content)

                    async with conn.begin():
                        await conn.execute(
                            text("INSERT INTO schema_migrations (filename) VALUES (:filename)"),
                            {"filename": path.name},
                        )

                    if verbose:
                        logger.info("Applied migration %s (autocommit=%s)", path.name, autocommit)
        finally:
            await _release_lock(lock_conn)


async def main() -> None:
    """Run migrations when executed as a script."""
    await apply_migrations()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
