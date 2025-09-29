"""Local filesystem storage implementation."""

from pathlib import Path

import aiofiles

from .base import AbstractStorage
from .exceptions import FileDeleteError, FileUploadError, StorageFileNotFoundError


class LocalStorage(AbstractStorage):
    """Local filesystem storage provider."""

    def __init__(self, base_path: str) -> None:
        """Initialize local storage with base path.

        Args:
            base_path: Base directory path for storing files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_full_path(self, key: str) -> Path:
        """Get full path for a storage key.

        Args:
            key: Storage key/filename

        Returns
        -------
            Full path to the file
        """
        return self.base_path / key

    async def upload(self, file_content: bytes, key: str) -> None:
        """Upload file content to local storage.

        Args:
            file_content: The file content as bytes
            key: The storage key/filename

        Raises
        ------
            FileUploadError: If the upload fails.
        """
        try:
            path = self._get_full_path(key)
            path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(path, "wb") as f:
                await f.write(file_content)
        except OSError as e:
            msg = f"Failed to upload file locally: {key}"
            raise FileUploadError(msg) from e

    async def get_download_url(self, key: str) -> str:
        """Get the file path for local storage.

        Args:
            key: The storage key/filename

        Returns
        -------
            Absolute file path as string

        Raises
        ------
            StorageFileNotFoundError: If the file does not exist.
        """
        path = self._get_full_path(key)
        if not path.exists():
            msg = f"File not found: {key}"
            raise StorageFileNotFoundError(msg)
        return str(path.absolute())

    async def download(self, key: str) -> bytes:
        """Return file bytes for local storage."""
        path = self._get_full_path(key)
        if not path.exists():
            msg = f"File not found: {key}"
            raise StorageFileNotFoundError(msg)
        async with aiofiles.open(path, "rb") as file_obj:
            return await file_obj.read()

    async def delete(self, key: str) -> None:
        """Delete a file from local storage.

        Args:
            key: The storage key/filename

        Raises
        ------
            FileDeleteError: If the deletion fails.
        """
        try:
            path = self._get_full_path(key)
            if path.exists():
                path.unlink()
        except OSError as e:
            msg = f"Failed to delete file locally: {key}"
            raise FileDeleteError(msg) from e
