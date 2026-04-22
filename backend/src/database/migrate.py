"""Lightweight SQL migration runner for PostgreSQL and transaction poolers."""

import logging
from collections.abc import Iterable
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from src.config.settings import Settings, get_settings
from src.database.engine import engine as default_engine


logger = logging.getLogger(__name__)
_MIGRATION_LOCK_KEY = "schema_migrations"
_VECTOR_SCHEMA_COLUMNS = (
    ("learning_memories", "vector", "MEMORY_EMBEDDING_OUTPUT_DIM"),
    ("mem0migrations", "vector", "MEMORY_EMBEDDING_OUTPUT_DIM"),
    ("rag_document_chunks", "embedding", "RAG_EMBEDDING_OUTPUT_DIM"),
    ("concepts", "embedding", "RAG_EMBEDDING_OUTPUT_DIM"),
)


def _migrations_dir() -> Path:
    return Path(__file__).parent / "migrations"


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


def _resolve_migration_files(settings: Settings | None = None) -> list[Path]:
    resolved_settings = settings or get_settings()
    migrations_dir = Path(resolved_settings.MIGRATIONS_DIR) if resolved_settings.MIGRATIONS_DIR else _migrations_dir()

    if not migrations_dir.exists():
        msg = f"Migration directory does not exist: {migrations_dir}"
        raise RuntimeError(msg)

    migration_files = _sorted_sql_files(migrations_dir)
    if migration_files:
        return migration_files

    msg = f"Migration directory has no SQL files: {migrations_dir}"
    raise RuntimeError(msg)


def _assert_transaction_safe_migration(path: Path, sql_content: str) -> None:
    normalized_sql = sql_content.upper()
    for fragment in (
        "-- AUTOCOMMIT",
        "CREATE INDEX CONCURRENTLY",
        "REINDEX CONCURRENTLY",
        "DROP INDEX CONCURRENTLY",
        "SET SEARCH_PATH",
        "SET LOCAL SEARCH_PATH",
        "PREPARE ",
        "DEALLOCATE ",
        "LISTEN ",
    ):
        if fragment in normalized_sql:
            msg = f"{path.name} uses unsupported pooled-connection migration SQL: {fragment.strip()}"
            raise RuntimeError(msg)


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


async def _schema_table_exists(conn: AsyncConnection) -> bool:
    result = await conn.execute(text("SELECT to_regclass('schema_migrations')"))
    return result.scalar_one_or_none() is not None


async def _get_applied(conn: AsyncConnection) -> Iterable[str]:
    result = await conn.execute(text("SELECT filename FROM schema_migrations"))
    return (row[0] for row in result)


async def _resolve_lock_key(conn: AsyncConnection) -> str:
    result = await conn.execute(text("SELECT current_schema()"))
    schema_name = result.scalar_one_or_none() or "public"
    return f"{_MIGRATION_LOCK_KEY}:{schema_name}"


async def _acquire_lock(conn: AsyncConnection, *, lock_key: str) -> None:
    await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:lock_key))"), {"lock_key": lock_key})


async def _execute_migration_sql(*, conn: AsyncConnection, sql_content: str) -> None:
    await conn.exec_driver_sql(sql_content)


async def _record_applied_migration(conn: AsyncConnection, *, filename: str) -> None:
    await conn.execute(
        text("INSERT INTO schema_migrations (filename) VALUES (:filename)"),
        {"filename": filename},
    )


async def _apply_pending_migrations(
    *,
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
        _assert_transaction_safe_migration(path, sql_content)
        await _execute_migration_sql(conn=conn, sql_content=sql_content)
        await _record_applied_migration(conn, filename=path.name)
        applied_count += 1

        if verbose:
            logger.info("migration.applied", extra={"migration_filename": path.name})

    return applied_count


async def _get_pending_migration_names(conn: AsyncConnection, *, migration_files: list[Path]) -> list[str]:
    if not await _schema_table_exists(conn):
        return [path.name for path in migration_files]

    applied = set(await _get_applied(conn))
    return [path.name for path in migration_files if path.name not in applied]


async def apply_migrations(db_engine: AsyncEngine | None = None) -> int:
    """Apply pending SQL migrations in order and return the number applied."""
    engine = db_engine or default_engine

    settings = get_settings()
    migration_files = _resolve_migration_files(settings)
    verbose = settings.MIGRATIONS_VERBOSE

    async with engine.connect() as conn, conn.begin():
        lock_key = await _resolve_lock_key(conn)
        await _acquire_lock(conn, lock_key=lock_key)
        await _ensure_schema_table(conn)
        applied = set(await _get_applied(conn))
        return await _apply_pending_migrations(
            conn=conn,
            migration_files=migration_files,
            applied=applied,
            verbose=verbose,
        )


async def assert_migrations_current(db_engine: AsyncEngine | None = None) -> None:
    """Raise if the target database has pending SQL migrations."""
    engine = db_engine or default_engine
    migration_files = _resolve_migration_files()

    async with engine.connect() as conn, conn.begin():
        lock_key = await _resolve_lock_key(conn)
        await _acquire_lock(conn, lock_key=lock_key)
        pending = await _get_pending_migration_names(conn, migration_files=migration_files)

    if pending:
        preview = ", ".join(pending[:5])
        remaining = len(pending) - min(len(pending), 5)
        suffix = f" (+{remaining} more)" if remaining else ""
        msg = f"Database has pending migrations: {preview}{suffix}"
        raise RuntimeError(msg)


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
    applied_count = await apply_migrations()
    logger.info("migration.run.completed", extra={"applied_count": applied_count})


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
