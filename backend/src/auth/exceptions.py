"""Authentication-specific exceptions."""

from fastapi import HTTPException, status


class InvalidTokenError(HTTPException):
    """Invalid token provided."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
