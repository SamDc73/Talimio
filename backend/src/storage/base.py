"""Abstract storage interface for different storage providers."""

from abc import ABC, abstractmethod


class AbstractStorage(ABC):
    """Abstract base class for storage providers."""

    @abstractmethod
    async def upload(self, file_content: bytes, key: str) -> None:
        """Upload file content to storage.

        Args:
            file_content: The file content as bytes
            key: The storage key/path for the file

        Raises
        ------
            FileUploadError: If the upload fails.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_download_url(self, key: str) -> str:
        """Get a download URL for the file.

        Args:
            key: The storage key/path for the file

        Returns
        -------
            URL string (presigned URL for cloud, file path for local).

        Raises
        ------
            StorageFileNotFoundError: If the file is not found.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a file from storage.

        Args:
            key: The storage key/path for the file

        Raises
        ------
            FileDeleteError: If the deletion fails.
        """
        raise NotImplementedError
