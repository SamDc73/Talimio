"""Cloudflare R2 storage implementation using aioboto3."""

from typing import Any

import aioboto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .base import AbstractStorage
from .exceptions import (
    CORSConfigError,
    FileDeleteError,
    FileDownloadError,
    FileUploadError,
)


class R2Storage(AbstractStorage):
    """Cloudflare R2 storage provider using aioboto3."""

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket_name: str,
        region: str = "auto",
    ) -> None:
        """Initialize R2 storage with credentials.

        Args:
            account_id: Cloudflare account ID
            access_key_id: R2 access key ID
            secret_access_key: R2 secret access key
            bucket_name: R2 bucket name
            region: R2 region (default: auto)
        """
        self.bucket_name = bucket_name
        self.endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.region = region
        self._session = aioboto3.Session()

    async def _get_client(self) -> Any:
        """Get an S3 client instance."""
        return self._session.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
            config=Config(signature_version="s3v4"),
        )

    async def upload(self, file_content: bytes, key: str) -> None:
        """Upload file content to R2 storage.

        Args:
            file_content: The file content as bytes.
            key: The storage key/filename.

        Raises
        ------
            FileUploadError: If the upload fails.
        """
        try:
            async with await self._get_client() as client:
                await client.put_object(
                    Bucket=self.bucket_name, Key=key, Body=file_content
                )
        except ClientError as e:
            msg = f"Failed to upload to R2: {key}"
            raise FileUploadError(msg) from e

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Generate a presigned URL for downloading from R2.

        Args:
            key: The storage key/filename.
            expires_in: URL expiration time in seconds.

        Returns
        -------
            A presigned URL for downloading the file.

        Raises
        ------
            FileDownloadError: If URL generation fails.
        """
        try:
            async with await self._get_client() as client:
                return await client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
        except ClientError as e:
            msg = f"Failed to generate R2 download URL for key: {key}"
            raise FileDownloadError(msg) from e

    async def delete(self, key: str) -> None:
        """Delete a file from R2 storage.

        Args:
            key: The storage key/filename.

        Raises
        ------
            FileDeleteError: If the deletion fails.
        """
        try:
            async with await self._get_client() as client:
                await client.delete_.object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            msg = f"Failed to delete from R2: {key}"
            raise FileDeleteError(msg) from e

    async def set_cors_policy(self) -> None:
        """Set CORS policy on the R2 bucket."""
        cors_configuration = {
            "CORSRules": [
                {
                    "AllowedHeaders": ["*"],
                    "AllowedMethods": ["GET", "PUT", "POST", "DELETE"],
                    "AllowedOrigins": ["*"],
                    "ExposeHeaders": [],
                    "MaxAgeSeconds": 3000,
                }
            ]
        }
        try:
            async with await self._get_client() as client:
                await client.put_bucket_cors(
                    Bucket=self.bucket_name,
                    CORSConfiguration=cors_configuration,
                )
        except ClientError as e:
            msg = f"Failed to set CORS policy on bucket {self.bucket_name}"
            raise CORSConfigError(msg) from e
