"""Transactional job enqueue through the caller's database session.

This mirrors ``procrastinate_defer_jobs_v1`` (a plain insert into
``procrastinate_jobs``) so the job row commits or rolls back atomically with
the evidence write that triggered it. Procrastinate's own ``defer_async`` uses
a separate connection pool and would enqueue outside the caller's transaction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


_DEFER_SQL = text(
    """
    INSERT INTO procrastinate_jobs (queue_name, task_name, priority, lock, queueing_lock, args, scheduled_at)
    VALUES (:queue, :task_name, :priority, :lock, :queueing_lock, CAST(:args AS jsonb), :scheduled_at)
    ON CONFLICT (queueing_lock) WHERE status = 'todo' DO NOTHING
    RETURNING id
    """
)


async def defer_job(
    session: AsyncSession,
    *,
    task_name: str,
    queue: str,
    args: Mapping[str, object] | None = None,
    queueing_lock: str | None = None,
    lock: str | None = None,
    priority: int = 0,
    scheduled_at: datetime | None = None,
) -> int | None:
    """Defer a procrastinate job inside the caller's transaction.

    Returns the new job id, or None when a job with the same queueing lock is
    already pending (duplicate work collapses instead of erroring).
    """
    result = await session.execute(
        _DEFER_SQL,
        {
            "queue": queue,
            "task_name": task_name,
            "priority": priority,
            "lock": lock,
            "queueing_lock": queueing_lock,
            "args": json.dumps(dict(args or {})),
            "scheduled_at": scheduled_at,
        },
    )
    return result.scalar_one_or_none()
