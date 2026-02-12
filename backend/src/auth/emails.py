"""Email utilities for local auth (password reset + verification)."""

from __future__ import annotations

import hashlib
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import httpx
import jwt

from src.auth.security import ALGORITHM, get_jwt_signing_key
from src.config.settings import get_settings


_BRAND_NAME = "Talimio"
_PRIMARY_COLOR = "#16a34a"  # Tailwind-ish green to match the app theme
_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS = 24
_RESEND_SEND_EMAILS_URL = "https://api.resend.com/emails"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PasswordResetClaims:
    """Decoded password reset claims."""

    email: str
    jti: str
    expires_at: datetime


@dataclass(frozen=True)
class EmailVerificationClaims:
    """Decoded email verification claims."""

    email: str


def _render_email_layout(*, preheader: str, title: str, body_html: str) -> str:
    year = datetime.now(UTC).year
    safe_preheader = preheader.replace("<", "&lt;").replace(">", "&gt;")
    safe_title = title.replace("<", "&lt;").replace(">", "&gt;")

    return f"""\
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta name="x-apple-disable-message-reformatting" />
    <title>{safe_title}</title>
  </head>
  <body style="margin:0; padding:0; background-color:#f6f8fb; font-family:Roboto, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;">
    <span style="display:none; visibility:hidden; opacity:0; color:transparent; height:0; width:0; overflow:hidden; mso-hide:all;">
      {safe_preheader}
    </span>

    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse; width:100%; background-color:#f6f8fb;">
      <tr>
        <td align="center" style="padding:24px 16px;">
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse; max-width:560px; background-color:#ffffff; border:1px solid #e5e7eb; border-radius:16px; overflow:hidden; box-shadow:0 24px 50px rgba(0,0,0,0.18);">
            <tr>
              <td style="padding:24px 24px 0 24px;">
                <div style="font-size:14px; font-weight:700; color:{_PRIMARY_COLOR}; letter-spacing:0.2px;">
                  {_BRAND_NAME}
                </div>
                <h1 style="margin:12px 0 0 0; font-size:22px; line-height:1.3; color:#0f172a;">
                  {safe_title}
                </h1>
              </td>
            </tr>
            <tr>
              <td style="padding:20px 24px 24px 24px;">
                {body_html}
              </td>
            </tr>
            <tr>
              <td style="padding:16px 24px; background-color:#f8fafc; border-top:1px solid #e5e7eb;">
                <div style="font-size:12px; line-height:1.5; color:#64748b;">
                  If you didn't request this email, you can safely ignore it.
                </div>
                <div style="margin-top:10px; font-size:12px; color:#94a3b8;">
                  © {year} {_BRAND_NAME}
                </div>
              </td>
            </tr>
          </table>
        </td>
      </tr>
    </table>
  </body>
</html>
"""


def _render_button(*, url: str, text: str) -> str:
    safe_url = url.replace("'", "%27")
    safe_text = text.replace("<", "&lt;").replace(">", "&gt;")

    return f"""\
<table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse:collapse; margin:18px 0 14px 0;">
  <tr>
    <td align="center" style="border-radius:12px;" bgcolor="{_PRIMARY_COLOR}">
      <a href="{safe_url}" style="display:inline-block; padding:12px 18px; font-size:14px; font-weight:700; color:#ffffff; text-decoration:none;">
        {safe_text}
      </a>
    </td>
  </tr>
</table>
"""


def _render_link_fallback(*, url: str) -> str:
    safe_url = url.replace("<", "&lt;").replace(">", "&gt;")
    return f"""\
<div style="margin-top:14px; font-size:12px; color:#64748b; line-height:1.6;">
  If the button doesn't work, copy and paste this link into your browser:
  <div style="margin-top:8px; padding:10px 12px; border:1px solid #e5e7eb; border-radius:12px; background-color:#f8fafc; word-break:break-all; color:#0f172a;">
    {safe_url}
  </div>
</div>
"""


def _build_idempotency_key(*, purpose: str, email: str, token: str) -> str:
    material = f"{purpose}:{email}:{token}"
    digest = hashlib.sha256(material.encode("utf-8")).hexdigest()[:24]
    return f"{purpose}/{digest}"


async def send_email(
    *,
    email_to: str,
    subject: str,
    html_content: str,
    idempotency_key: str | None = None,
) -> None:
    """Send an email through the Resend API when configured; otherwise do nothing."""
    settings = get_settings()
    resend_api_key = settings.RESEND_API_KEY.get_secret_value()
    if not resend_api_key or not settings.EMAILS_FROM_EMAIL:
        return

    from_email = settings.EMAILS_FROM_EMAIL
    if settings.EMAILS_FROM_NAME:
        from_email = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"

    headers: dict[str, str] = {
        "Authorization": f"Bearer {resend_api_key}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    payload = {
        "from": from_email,
        "to": [email_to],
        "subject": subject,
        "html": html_content,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(_RESEND_SEND_EMAILS_URL, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError):
        logger.exception("Failed to send auth email via Resend API")
        raise

    if not isinstance(data, dict):
        return

    email_id = data.get("id")
    if not isinstance(email_id, str):
        return

    logger.info("Sent auth email via Resend API", extra={"resend_email_id": email_id, "email_to": email_to})


def generate_password_reset_token(email: str) -> str:
    """Generate a signed password reset token bound to an email address."""
    settings = get_settings()
    delta = timedelta(hours=settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS)
    now = datetime.now(UTC)
    expires = now + delta
    return jwt.encode(
        {"exp": expires, "jti": uuid.uuid4().hex, "nbf": now, "sub": email},
        get_jwt_signing_key(),
        algorithm=ALGORITHM,
    )


def generate_email_verification_token(email: str) -> str:
    """Generate a signed email-verification token bound to an email address."""
    now = datetime.now(UTC)
    expires = now + timedelta(hours=_EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    return jwt.encode(
        {"exp": expires, "nbf": now, "sub": email, "typ": "verify_email"},
        get_jwt_signing_key(),
        algorithm=ALGORITHM,
    )


def verify_password_reset_token(token: str) -> PasswordResetClaims | None:
    """Verify reset token and return decoded claims if valid."""
    try:
        payload = jwt.decode(token, get_jwt_signing_key(), algorithms=[ALGORITHM])
        email = str(payload["sub"])
        jti = str(payload["jti"])
        expires_raw = payload["exp"]
        if isinstance(expires_raw, (int, float)):
            expires_at = datetime.fromtimestamp(expires_raw, tz=UTC)
        elif isinstance(expires_raw, datetime):
            expires_at = expires_raw if expires_raw.tzinfo else expires_raw.replace(tzinfo=UTC)
        else:
            return None
        return PasswordResetClaims(email=email, jti=jti, expires_at=expires_at)
    except (jwt.InvalidTokenError, KeyError):
        return None


def verify_email_verification_token(token: str) -> EmailVerificationClaims | None:
    """Verify email verification token and return decoded claims if valid."""
    try:
        payload = jwt.decode(token, get_jwt_signing_key(), algorithms=[ALGORITHM])
        claim_type = payload["typ"]
        email = payload["sub"]
        if claim_type != "verify_email":
            return None
        return EmailVerificationClaims(email=str(email))
    except (jwt.InvalidTokenError, KeyError):
        return None


async def send_reset_email(*, email: str, token: str) -> None:
    """Send password reset email."""
    settings = get_settings()
    link = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={token}"
    expires_in = settings.EMAIL_RESET_TOKEN_EXPIRE_HOURS
    expires_text = "1 hour" if expires_in == 1 else f"{expires_in} hours"

    body = f"""\
<p style="margin:0; font-size:14px; line-height:1.6; color:#475569;">
  We received a request to reset your password. Click the button below to choose a new one.
</p>
{_render_button(url=link, text="Reset password")}
<p style="margin:0; font-size:12px; line-height:1.6; color:#64748b;">
  This link expires in {expires_text}.
</p>
{_render_link_fallback(url=link)}
"""
    idempotency_key = _build_idempotency_key(purpose="auth-reset", email=email, token=token)
    await send_email(
        email_to=email,
        subject="Reset your Talimio password",
        html_content=_render_email_layout(preheader="Reset your password", title="Reset your password", body_html=body),
        idempotency_key=idempotency_key,
    )


async def send_verification_email(*, email: str, token: str) -> None:
    """Send email verification email."""
    settings = get_settings()
    link = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={token}"
    body = f"""\
<p style="margin:0; font-size:14px; line-height:1.6; color:#475569;">
  Confirm your email to finish setting up your account.
</p>
{_render_button(url=link, text="Verify email")}
{_render_link_fallback(url=link)}
"""
    idempotency_key = _build_idempotency_key(purpose="auth-verify", email=email, token=token)
    await send_email(
        email_to=email,
        subject="Verify your Talimio email",
        html_content=_render_email_layout(preheader="Verify your email", title="Verify your email", body_html=body),
        idempotency_key=idempotency_key,
    )
