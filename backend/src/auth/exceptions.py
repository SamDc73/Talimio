"""Authentication-specific exceptions."""

from fastapi import HTTPException, status


class AuthenticationError(HTTPException):
    """Base authentication error."""

    def __init__(self, detail: str = "Authentication failed") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class InvalidCredentialsError(AuthenticationError):
    """Invalid credentials provided."""

    def __init__(self) -> None:
        super().__init__(detail="Invalid email or password")


class TokenExpiredError(AuthenticationError):
    """Token has expired."""

    def __init__(self) -> None:
        super().__init__(detail="Token has expired")


class InvalidTokenError(AuthenticationError):
    """Invalid token provided."""

    def __init__(self) -> None:
        super().__init__(detail="Invalid token")


class UserNotFoundError(HTTPException):
    """User not found."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


class UserAlreadyExistsError(HTTPException):
    """User already exists."""

    def __init__(self) -> None:
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail="User already exists")


class AuthProviderNotConfiguredError(HTTPException):
    """Auth provider not properly configured."""

    def __init__(self, provider: str) -> None:
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication provider '{provider}' is not properly configured"
        )
