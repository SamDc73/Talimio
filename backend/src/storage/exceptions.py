"""Custom exceptions for the storage module."""


class StorageError(Exception):
    """Base exception for storage operations."""


class FileUploadError(StorageError):
    """Raised when a file upload fails."""


class FileDownloadError(StorageError):
    """Raised when a file download fails."""


class FileDeleteError(StorageError):
    """Raised when a file delete fails."""


class StorageFileNotFoundError(StorageError):
    """Raised when a file is not found in storage."""


class CORSConfigError(StorageError):
    """Raised when configuring CORS fails."""
