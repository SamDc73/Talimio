"""Server-side password policy checks."""

from __future__ import annotations

import re

from src.config.settings import get_settings


class PasswordPolicyError(ValueError):
    """Raised when a password does not satisfy policy requirements."""


def validate_password_policy(password: str) -> None:
    """Validate local password policy."""
    settings = get_settings()
    issues: list[str] = []

    if len(password) < settings.AUTH_PASSWORD_MIN_LENGTH:
        issues.append(f"must be at least {settings.AUTH_PASSWORD_MIN_LENGTH} characters")
    if settings.AUTH_PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        issues.append("must include an uppercase letter")
    if settings.AUTH_PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        issues.append("must include a lowercase letter")
    if settings.AUTH_PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        issues.append("must include a number")
    if settings.AUTH_PASSWORD_REQUIRE_SYMBOL and not re.search(r"[^A-Za-z0-9]", password):
        issues.append("must include a special character")
    if settings.AUTH_PASSWORD_DISALLOW_WHITESPACE and any(character.isspace() for character in password):
        issues.append("must not include whitespace")

    if issues:
        issue_list = "; ".join(issues)
        message = f"Password policy violation: {issue_list}."
        raise PasswordPolicyError(message)

