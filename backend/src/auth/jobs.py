"""Off-request password-reset email delivery.

``forgot-password`` must return in the same time whether or not the account
exists, otherwise the response latency leaks which emails are registered. The
request unconditionally defers this job, so the account lookup, token mint, and
outbound Resend call all happen here in the worker — the request path does the
same work for every email.

The job silently no-ops for unknown or inactive accounts, and the reset token
is minted here rather than passed as a job argument so a live, usable token
never sits in ``procrastinate_jobs.args``.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.jobs import QUEUE_AUTH, defer_job


logger = logging.getLogger(__name__)

PASSWORD_RESET_EMAIL_TASK_NAME = "auth.send_password_reset_email"  # noqa: S105 — procrastinate task name, not a secret


async def defer_password_reset_email(session: AsyncSession, *, email: str) -> int | None:
    """Enqueue a password-reset email inside the caller's transaction."""
    return await defer_job(
        session,
        task_name=PASSWORD_RESET_EMAIL_TASK_NAME,
        queue=QUEUE_AUTH,
        args={"email": email},
    )


async def run_password_reset_email(*, email: str) -> None:
    """Job body: look up the account, mint a reset token, and send the email.

    No-ops for unknown or inactive accounts so the request can defer this job
    unconditionally without leaking whether the email is registered.
    """
    from src.auth import crud as local_crud
    from src.auth.emails import generate_password_reset_token, send_reset_email
    from src.database.session import async_session_maker

    normalized_email = local_crud.normalize_email(email)
    async with async_session_maker() as session:
        user = await local_crud.get_user_by_email(session, normalized_email)

    if not user or not user.is_active:
        logger.info("jobs.password_reset_email.skipped")
        return

    token = generate_password_reset_token(normalized_email)
    await send_reset_email(email=normalized_email, token=token)
    logger.info("jobs.password_reset_email.sent", extra={"user_id": str(user.id)})
