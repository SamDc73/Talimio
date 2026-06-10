"""Background task definitions."""

from __future__ import annotations

import logging
import uuid

import procrastinate

from src.jobs.app import QUEUE_MAINTENANCE, QUEUE_MEMORY, job_app


logger = logging.getLogger(__name__)


@job_app.task(
    name="memory.run_profile_maintenance",
    queue=QUEUE_MEMORY,
    retry=procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def run_profile_maintenance(user_id: str) -> None:
    """Evaluate a user's unprocessed chat turns for durable profile memory."""
    from src.memory.maintenance import process_user_memory

    evaluated = await process_user_memory(uuid.UUID(user_id))
    logger.info("jobs.profile_maintenance.done", extra={"memory_user_id": user_id, "turns_evaluated": evaluated})


@job_app.periodic(cron="*/10 * * * *")
@job_app.task(queue=QUEUE_MAINTENANCE, queueing_lock="maintenance:retry-stalled-jobs")
async def retry_stalled_jobs(timestamp: int) -> None:
    """Re-queue jobs whose worker stopped heartbeating (crash or hard kill)."""
    del timestamp
    stalled_jobs = await job_app.job_manager.get_stalled_jobs()
    for job in stalled_jobs:
        logger.warning("jobs.stalled.retried", extra={"job_id": job.id, "job_task_name": job.task_name})
        await job_app.job_manager.retry_job(job)
