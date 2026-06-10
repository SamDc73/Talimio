"""Background task definitions.

Memory and pedagogy tasks land here in later phases; for now this module owns
the periodic stalled-job sweep that recovers work from crashed workers.
"""

from __future__ import annotations

import logging

from src.jobs.app import QUEUE_MAINTENANCE, job_app


logger = logging.getLogger(__name__)


@job_app.periodic(cron="*/10 * * * *")
@job_app.task(queue=QUEUE_MAINTENANCE, queueing_lock="maintenance:retry-stalled-jobs")
async def retry_stalled_jobs(timestamp: int) -> None:
    """Re-queue jobs whose worker stopped heartbeating (crash or hard kill)."""
    del timestamp
    stalled_jobs = await job_app.job_manager.get_stalled_jobs()
    for job in stalled_jobs:
        logger.warning("jobs.stalled.retried", extra={"job_id": job.id, "job_task_name": job.task_name})
        await job_app.job_manager.retry_job(job)
