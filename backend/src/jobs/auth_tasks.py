"""Procrastinate tasks for transactional auth emails.

These wrap the job bodies in ``src.auth.jobs``. Delivery runs out-of-request so
``forgot-password`` cannot leak account existence through response latency, and
retries on transient Resend failures so a single network blip does not drop a
password-reset email.
"""

from __future__ import annotations

import logging

import procrastinate

from src.jobs.app import QUEUE_AUTH, job_app


logger = logging.getLogger(__name__)


@job_app.task(
    name="auth.send_password_reset_email",
    queue=QUEUE_AUTH,
    retry=procrastinate.RetryStrategy(max_attempts=3, exponential_wait=5),
)
async def send_password_reset_email(email: str) -> None:
    """Mint a reset token and send the reset email out-of-request."""
    from src.auth.jobs import run_password_reset_email

    await run_password_reset_email(email=email)
