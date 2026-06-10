"""Procrastinate application: queue names, lock conventions, and the connector.

Queues:
- ``memory``      core profile maintenance jobs
- ``pedagogy``    pedagogical updater jobs
- ``maintenance`` rebuilds, decay passes, and sweeps

Queueing locks serialize pending work per subject; the partial unique index on
``procrastinate_jobs (queueing_lock) WHERE status = 'todo'`` collapses duplicates.
"""

from __future__ import annotations

import uuid

import procrastinate

from src.config.settings import get_settings


QUEUE_MEMORY = "memory"
QUEUE_PEDAGOGY = "pedagogy"
QUEUE_MAINTENANCE = "maintenance"


def memory_queueing_lock(user_id: uuid.UUID | str) -> str:
    """Queueing lock that serializes core-memory maintenance per user."""
    return f"memory:user:{user_id}"


def pedagogy_queueing_lock(user_id: uuid.UUID | str, course_id: uuid.UUID | str) -> str:
    """Queueing lock that serializes pedagogical updates per learner-course pair."""
    return f"pedagogy:{user_id}:{course_id}"


def psycopg_conninfo() -> str:
    """Plain libpq conninfo derived from the SQLAlchemy DATABASE_URL."""
    return get_settings().DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)


job_app = procrastinate.App(
    connector=procrastinate.PsycopgConnector(conninfo=psycopg_conninfo()),
    import_paths=["src.jobs.tasks"],
)
