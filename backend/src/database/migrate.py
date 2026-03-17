"""Lightweight SQL migration runner for PostgreSQL session poolers."""

import logging
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.config.settings import Settings, get_settings
from src.database.engine import engine as default_engine


logger = logging.getLogger(__name__)
_MIGRATION_LOCK_KEY = "schema_migrations"
_AUTOCOMMIT_TAG = "-- autocommit"
_VECTOR_SCHEMA_COLUMNS = (
    ("learning_memories", "vector", "MEMORY_EMBEDDING_OUTPUT_DIM"),
    ("mem0migrations", "vector", "MEMORY_EMBEDDING_OUTPUT_DIM"),
    ("rag_document_chunks", "embedding", "RAG_EMBEDDING_OUTPUT_DIM"),
    ("concepts", "embedding", "RAG_EMBEDDING_OUTPUT_DIM"),
)


def _migrations_dir() -> Path:
    return Path(__file__).parent / "migrations"


def _is_autocommit(sql: str) -> bool:
    return sql.lstrip().lower().startswith(_AUTOCOMMIT_TAG)


def _read_sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _resolve_embedding_output_dimensions(settings: Settings | None = None) -> tuple[int, int]:
    """Return configured RAG and memory vector dimensions."""
    resolved_settings = settings or get_settings()
    rag_dim = resolved_settings.RAG_EMBEDDING_OUTPUT_DIM
    mem_dim = resolved_settings.MEMORY_EMBEDDING_OUTPUT_DIM

    if rag_dim is None:
        msg = "RAG_EMBEDDING_OUTPUT_DIM must be set before running migrations or startup checks"
        raise ValueError(msg)
    if mem_dim is None:
        msg = "MEMORY_EMBEDDING_OUTPUT_DIM must be set before running migrations or startup checks"
        raise ValueError(msg)

    return rag_dim, mem_dim


def _build_expected_vector_dimensions(settings: Settings | None = None) -> dict[tuple[str, str], int]:
    """Map vector columns to the configured dimensions they must use."""
    rag_dim, mem_dim = _resolve_embedding_output_dimensions(settings)
    return {
        ("learning_memories", "vector"): mem_dim,
        ("mem0migrations", "vector"): mem_dim,
        ("rag_document_chunks", "embedding"): rag_dim,
        ("concepts", "embedding"): rag_dim,
    }


def _interpolate_sql_placeholders(sql: str, settings: Settings | None = None) -> str:
    """Replace vector-dimension placeholders in SQL with canonical settings values."""
    rag_dim, mem_dim = _resolve_embedding_output_dimensions(settings)
    return sql.replace("${RAG_EMBEDDING_OUTPUT_DIM}", str(rag_dim)).replace(
        "${MEMORY_EMBEDDING_OUTPUT_DIM}",
        str(mem_dim),
    )


async def _fetch_vector_dimension(
    conn: AsyncConnection,
    *,
    table_name: str,
    column_name: str,
) -> int | None:
    """Read a pgvector column dimension from PostgreSQL metadata."""
    result = await conn.execute(
        text(
            """
            SELECT attribute.atttypmod
            FROM pg_attribute AS attribute
            JOIN pg_class AS class ON class.oid = attribute.attrelid
            JOIN pg_namespace AS namespace ON namespace.oid = class.relnamespace
            WHERE namespace.nspname = current_schema()
              AND class.relname = :table_name
              AND attribute.attname = :column_name
              AND attribute.attnum > 0
              AND NOT attribute.attisdropped
            """
        ),
        {"table_name": table_name, "column_name": column_name},
    )
    raw_dimension = result.scalar_one_or_none()
    if raw_dimension is None or raw_dimension <= 0:
        return None
    return int(raw_dimension)


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

        sql_content = _interpolate_sql_placeholders(_read_sql(path))
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


async def validate_vector_schema_dimensions(db_engine: AsyncEngine | None = None) -> None:
    """Ensure configured vector dimensions match the live database schema."""
    engine = db_engine or default_engine
    expected_dimensions = _build_expected_vector_dimensions()
    rag_dim, mem_dim = _resolve_embedding_output_dimensions()
    mismatches: list[str] = []

    async with engine.connect() as conn:
        for table_name, column_name, _setting_name in _VECTOR_SCHEMA_COLUMNS:
            expected_dimension = expected_dimensions[table_name, column_name]
            actual_dimension = await _fetch_vector_dimension(
                conn,
                table_name=table_name,
                column_name=column_name,
            )
            if actual_dimension is None:
                mismatches.append(f"{table_name}.{column_name}=missing")
                continue
            if actual_dimension != expected_dimension:
                mismatches.append(
                    f"{table_name}.{column_name}=database:{actual_dimension},configured:{expected_dimension}"
                )

    if mismatches:
        details = "; ".join(mismatches)
        msg = f"Vector schema dimensions do not match configuration: {details}"
        raise RuntimeError(msg)

    logger.info(
        "startup.vector_schema_dimensions.validated",
        extra={
            "rag_dimension": rag_dim,
            "memory_dimension": mem_dim,
            "validated_columns": len(_VECTOR_SCHEMA_COLUMNS),
        },
    )


async def main() -> None:
    """Run migrations when executed as a script."""
    _ = await apply_migrations()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
