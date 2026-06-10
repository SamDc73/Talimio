"""Background task definitions."""

from __future__ import annotations

import contextlib
import logging
import uuid

import procrastinate
import procrastinate.exceptions

from src.jobs.app import QUEUE_MAINTENANCE, QUEUE_MEMORY, QUEUE_PEDAGOGY, job_app, pedagogy_queueing_lock


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


@job_app.task(name="memory.rebuild_user_profile", queue=QUEUE_MAINTENANCE)
async def rebuild_user_profile(user_id: str, apply: bool = False) -> None:
    """Replay the evidence log against live inferred state; optionally repair."""
    from src.database.session import async_session_maker
    from src.memory.rebuild import diff_inferred_profile, repair_inferred_profile

    async with async_session_maker() as session:
        if apply:
            drifts = await repair_inferred_profile(session, uuid.UUID(user_id))
            await session.commit()
        else:
            drifts = await diff_inferred_profile(session, uuid.UUID(user_id))

    for drift in drifts:
        logger.warning(
            "jobs.profile_rebuild.drift",
            extra={
                "memory_user_id": user_id,
                "drift_slot": drift.slot,
                "live_value": drift.live_value,
                "rebuilt_value": drift.rebuilt_value,
                "repaired": apply,
            },
        )
    logger.info("jobs.profile_rebuild.done", extra={"memory_user_id": user_id, "drift_count": len(drifts)})


@job_app.task(
    name="pedagogy.run_student_card_update",
    queue=QUEUE_PEDAGOGY,
    retry=procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def run_student_card_update(user_id: str, course_id: str) -> None:
    """Consolidate one learner-course pair's new evidence into the StudentCard."""
    from src.memory.pedagogy_updater import process_pedagogy_update

    processed = await process_pedagogy_update(uuid.UUID(user_id), uuid.UUID(course_id))
    logger.info(
        "jobs.pedagogy_update.done",
        extra={"memory_user_id": user_id, "course_id": course_id, "evidence_processed": processed},
    )


@job_app.task(
    name="pedagogy.forget_cleanup",
    queue=QUEUE_MAINTENANCE,
    retry=procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def forget_pedagogy_cleanup(user_id: str, course_id: str, cutoff: str) -> None:
    """Redact learner-authored pedagogical evidence after an explicit forget."""
    from datetime import datetime

    from src.memory.pedagogy_controls import run_forget_cleanup

    await run_forget_cleanup(uuid.UUID(user_id), uuid.UUID(course_id), datetime.fromisoformat(cutoff))
    logger.info("jobs.pedagogy_forget_cleanup.done", extra={"memory_user_id": user_id, "course_id": course_id})


@job_app.task(name="pedagogy.rebuild_student_card", queue=QUEUE_MAINTENANCE)
async def rebuild_student_card(user_id: str, course_id: str, apply: bool = False) -> None:
    """Compare the live StudentCard against its latest revision snapshot; optionally repair."""
    from src.database.session import async_session_maker
    from src.memory.pedagogy_rebuild import diff_student_card, repair_student_card

    async with async_session_maker() as session:
        if apply:
            drift = await repair_student_card(
                session, user_id=uuid.UUID(user_id), course_id=uuid.UUID(course_id)
            )
            await session.commit()
        else:
            drift = await diff_student_card(
                session, user_id=uuid.UUID(user_id), course_id=uuid.UUID(course_id)
            )

    if drift is not None:
        logger.warning(
            "jobs.pedagogy_rebuild.drift",
            extra={
                "memory_user_id": user_id,
                "course_id": course_id,
                "card_id": str(drift.card_id),
                "live_revision": drift.live_revision,
                "snapshot_revision": drift.snapshot_revision,
                "repaired": apply,
            },
        )
    logger.info(
        "jobs.pedagogy_rebuild.done",
        extra={"memory_user_id": user_id, "course_id": course_id, "drift_count": 0 if drift is None else 1},
    )


@job_app.periodic(cron="0 3 * * *")
@job_app.task(name="pedagogy.nightly_sweep", queue=QUEUE_MAINTENANCE, queueing_lock="pedagogy:nightly-sweep")
async def pedagogy_nightly_sweep(timestamp: int) -> None:
    """Defer the updater for every learner-course pair with evidence past its watermark."""
    del timestamp
    from src.database.session import async_session_maker
    from src.memory.pedagogy_updater import find_stale_pairs

    async with async_session_maker() as session:
        pairs = await find_stale_pairs(session)

    for user_id, course_id in pairs:
        with contextlib.suppress(procrastinate.exceptions.AlreadyEnqueued):
            await run_student_card_update.configure(
                queueing_lock=pedagogy_queueing_lock(user_id, course_id)
            ).defer_async(user_id=str(user_id), course_id=str(course_id))
    logger.info("jobs.pedagogy_sweep.done", extra={"pair_count": len(pairs)})


@job_app.periodic(cron="*/10 * * * *")
@job_app.task(queue=QUEUE_MAINTENANCE, queueing_lock="maintenance:retry-stalled-jobs")
async def retry_stalled_jobs(timestamp: int) -> None:
    """Re-queue jobs whose worker stopped heartbeating (crash or hard kill)."""
    del timestamp
    stalled_jobs = await job_app.job_manager.get_stalled_jobs()
    for job in stalled_jobs:
        logger.warning("jobs.stalled.retried", extra={"job_id": job.id, "job_task_name": job.task_name})
        await job_app.job_manager.retry_job(job)
