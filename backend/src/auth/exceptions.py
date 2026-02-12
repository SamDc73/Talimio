"""Authentication-specific exceptions."""

from fastapi import HTTPException, status


class InvalidTokenError(HTTPException):
    """Invalid token provided."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


class TokenExpiredError(HTTPException):
    """Token has expired."""

    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
