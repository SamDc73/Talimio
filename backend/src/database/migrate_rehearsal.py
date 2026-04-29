"""Rehearse database migrations against a Neon preview branch.

Creates an instant copy-on-write clone of the production database via
the Neon API, runs pending SQL migrations against it, and deletes the
branch.  Used in Cloud Build to validate migrations before they touch
production.

Required env vars
-----------------
NEON_API_KEY      Neon API key (from Secret Manager)
NEON_PROJECT_ID   Neon project ID (from Secret Manager)
COMMIT_SHA        Git commit SHA (set automatically by Cloud Build)
"""

import json
import logging
import urllib.request

from pydantic import SecretStr
from sqlalchemy.ext.asyncio import create_async_engine

from src.config.settings import Settings
from src.database.migrate import apply_migrations


logger = logging.getLogger(__name__)

_NEON_API_BASE = "https://console.neon.tech/api/v2"


def _neon_headers(api_key: str) -> dict[str, str]:
    """Build common Neon API request headers."""
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _create_branch(api_key: str, project_id: str, name: str) -> tuple[str, str]:
    """Create a Neon branch and return (branch_id, connection_uri)."""
    url = f"{_NEON_API_BASE}/projects/{project_id}/branches"
    payload = json.dumps(
        {
            "branch": {"name": name},
            "endpoints": [{"type": "read_write"}],
        }
    ).encode()

    req = urllib.request.Request(url, data=payload, headers=_neon_headers(api_key))  # noqa: S310
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        data = json.loads(resp.read())

    branch_id: str = data["branch"]["id"]
    db_url: str = data["connection_uris"][0]["connection_uri"]
    # Our app requires the psycopg driver prefix.
    db_url = db_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return branch_id, db_url


def _delete_branch(api_key: str, project_id: str, branch_id: str) -> None:
    """Delete a Neon branch (best-effort cleanup)."""
    url = f"{_NEON_API_BASE}/projects/{project_id}/branches/{branch_id}"
    headers = _neon_headers(api_key)
    headers.pop("Content-Type")
    req = urllib.request.Request(url, method="DELETE", headers=headers)  # noqa: S310
    try:
        urllib.request.urlopen(req, timeout=30)  # noqa: S310
        logger.info("neon.branch_deleted", extra={"branch_id": branch_id})
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "neon.branch_delete_failed",
            extra={"branch_id": branch_id, "error": str(exc)},
        )


async def _run_rehearsal_migrations(db_url: str, settings: Settings) -> None:
    """Run migrations against the temporary Neon branch."""
    engine = create_async_engine(
        db_url,
        echo=False,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )
    try:
        applied_count = await apply_migrations(engine, settings=settings)
        logger.info("neon.rehearsal_migrations_applied", extra={"applied_count": applied_count})
    finally:
        await engine.dispose()


async def main() -> None:
    """Create a Neon preview branch, run migrations, and clean up."""
    settings = Settings(
        AUTH_SECRET_KEY=SecretStr("neon-rehearsal-key"),
        DATABASE_URL="postgresql+psycopg://unused:unused@localhost/unused",
    )
    api_key = settings.NEON_API_KEY.get_secret_value().strip()
    project_id = settings.NEON_PROJECT_ID.strip()
    commit_sha = settings.COMMIT_SHA.strip() or "local"
    if not api_key:
        msg = "NEON_API_KEY environment variable is required"
        raise RuntimeError(msg)
    if not project_id:
        msg = "NEON_PROJECT_ID environment variable is required"
        raise RuntimeError(msg)

    branch_name = f"deploy-check-{commit_sha[:12]}"

    logger.info("neon.creating_preview_branch", extra={"branch_name": branch_name})
    branch_id, db_url = _create_branch(api_key, project_id, branch_name)
    logger.info("neon.preview_branch_created", extra={"branch_id": branch_id})

    try:
        rehearsal_settings = settings.model_copy(update={"DATABASE_URL": db_url})
        await _run_rehearsal_migrations(db_url, rehearsal_settings)
        logger.info("neon.rehearsal_passed")
    finally:
        _delete_branch(api_key, project_id, branch_id)


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    asyncio.run(main())
