"""Shared auth-mode enum for integration coverage."""

from enum import StrEnum


class AuthMode(StrEnum):
    """Supported authentication modes exercised by tests."""

    SINGLE_USER = "single_user"
    MULTI_USER = "multi_user"
