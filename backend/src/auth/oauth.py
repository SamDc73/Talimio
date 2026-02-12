"""Google OAuth helpers for local auth."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
from fastapi import HTTPException, Request, status
from httpx_oauth.clients.google import GoogleOAuth2

from src.config.settings import get_settings


_GOOGLE_OAUTH_FLOW_SESSION_KEY = "google_oauth_flow"
_GOOGLE_OAUTH_MAX_AGE_SECONDS = 600


@dataclass(frozen=True)
class GoogleOAuthIdentity:
    """Decoded Google identity fields required by local auth."""

    provider_user_id: str
    email: str


def get_google_client() -> GoogleOAuth2 | None:
    """Return Google OAuth client when configured."""
    settings = get_settings()
    google_client_secret = settings.GOOGLE_OAUTH_CLIENT_SECRET.get_secret_value()
    if not settings.GOOGLE_OAUTH_CLIENT_ID or not google_client_secret:
        return None
    return GoogleOAuth2(settings.GOOGLE_OAUTH_CLIENT_ID, google_client_secret)


def store_google_oauth_state(request: Request, *, state: str, nonce: str) -> None:
    """Persist OAuth state/nonce in session storage for callback validation."""
    request.session[_GOOGLE_OAUTH_FLOW_SESSION_KEY] = {
        "state": state,
        "nonce": nonce,
        "issued_at": int(datetime.now(UTC).timestamp()),
    }


def consume_google_oauth_state(request: Request) -> tuple[str, str]:
    """Load and clear OAuth state/nonce from session storage."""
    flow_state = request.session.pop(_GOOGLE_OAUTH_FLOW_SESSION_KEY, None)
    if not isinstance(flow_state, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    state = flow_state.get("state")
    nonce = flow_state.get("nonce")
    issued_at = flow_state.get("issued_at")
    if not isinstance(state, str) or not isinstance(nonce, str) or not isinstance(issued_at, int):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")

    age_seconds = int(datetime.now(UTC).timestamp()) - issued_at
    if age_seconds < 0 or age_seconds > _GOOGLE_OAUTH_MAX_AGE_SECONDS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth request expired")

    return state, nonce


def validate_google_id_token_nonce(id_token: object, *, expected_nonce: str) -> None:
    """Validate nonce inside Google id_token payload."""
    if not isinstance(id_token, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth response")

    try:
        claims = jwt.decode(
            id_token,
            options={
                "verify_signature": False,
                "verify_exp": False,
                "verify_nbf": False,
                "verify_iat": False,
                "verify_aud": False,
            },
        )
    except jwt.InvalidTokenError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth response") from error

    if not isinstance(claims, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth response")

    nonce = claims.get("nonce")
    if not isinstance(nonce, str):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth nonce")
    if not secrets.compare_digest(nonce, expected_nonce):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth nonce")


async def exchange_google_code_for_identity(
    client: GoogleOAuth2,
    *,
    code: str,
    redirect_uri: str,
    expected_nonce: str,
) -> GoogleOAuthIdentity:
    """Exchange OAuth code and return validated Google identity."""
    token = await client.get_access_token(code, redirect_uri=redirect_uri)
    validate_google_id_token_nonce(token.get("id_token"), expected_nonce=expected_nonce)

    access_token = token.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth response")

    google_user_id, email = await client.get_id_email(access_token)
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Google did not provide an email address")

    return GoogleOAuthIdentity(provider_user_id=str(google_user_id), email=email)
