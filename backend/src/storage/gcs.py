"""Google Cloud Storage implementation using S3-compatible XML API via aioboto3.

GCS exposes an S3-compatible XML API endpoint at https://storage.googleapis.com
which supports the full S3 multipart-upload flow.  We use aioboto3 with HMAC
credentials (not OAuth) so that every primitive—simple PUT, multipart initiate,
per-part presigned URLs, and multipart completion—can be handled with a single
async client.

Why not google-cloud-storage?
- The official JSON client cannot generate presigned URLs for multipart parts.
- The Transfer Manager is server-side-only (process pools) and is useless for
  browser-direct parallel uploads.
- The XML API is the only GCS surface that exposes S3-style multipart uploads
  with presigned per-part URLs.

References
----------
- https://cloud.google.com/storage/docs/aws-simple-migration
- https://cloud.google.com/storage/docs/xml-api/post-object-multipart
"""

from contextlib import AbstractAsyncContextManager
from typing import Protocol, cast

import aioboto3
from botocore.client import Config
from botocore.exceptions import ClientError

from .base import AbstractStorage, StorageUploadSession
from .exceptions import (
    FileDeleteError,
    FileDownloadError,
    FileUploadError,
    StorageFileNotFoundError,
)


class _S3Body(Protocol):
    async def read(self) -> bytes: ...


class _S3Client(Protocol):
    async def put_object(self, **kwargs: object) -> object: ...

    async def get_object(self, **kwargs: object) -> dict[str, _S3Body]: ...

    async def delete_object(self, **kwargs: object) -> object: ...

    async def generate_presigned_url(self, **kwargs: object) -> str: ...

    async def create_multipart_upload(self, **kwargs: object) -> dict[str, str]: ...

    async def complete_multipart_upload(self, **kwargs: object) -> dict[str, object]: ...

    async def abort_multipart_upload(self, **kwargs: object) -> object: ...

    async def list_parts(self, **kwargs: object) -> dict[str, object]: ...


class GCSStorage(AbstractStorage):
    """GCS storage provider using the S3-compatible XML API (aioboto3)."""

    _ENDPOINT_URL = "https://storage.googleapis.com"

    def __init__(
        self,
        *,
        bucket_name: str,
        hmac_access_key_id: str,
        hmac_secret_key: str,
        region: str | None = None,
    ) -> None:
        self.bucket_name = bucket_name
        self.hmac_access_key_id = hmac_access_key_id
        self.hmac_secret_key = hmac_secret_key
        self.region = region
        self._session = aioboto3.Session()

    # boto3 1.36+ auto-injects x-amz-checksum-* headers on PUT which GCS XML
    # API rejects with SignatureDoesNotMatch.  Disable auto checksums so
    # presigned URL / direct PUT flows work.
    _BOTO_CONFIG = Config(
        signature_version="s3v4",
        request_checksum_calculation="WHEN_REQUIRED",
        response_checksum_validation="WHEN_REQUIRED",
    )

    async def _get_client(self) -> AbstractAsyncContextManager[_S3Client]:
        """Return an async S3 client configured for GCS XML API."""
        return cast(
            "AbstractAsyncContextManager[_S3Client]",
            self._session.client(
                "s3",
                endpoint_url=self._ENDPOINT_URL,
                aws_access_key_id=self.hmac_access_key_id,
                aws_secret_access_key=self.hmac_secret_key,
                region_name=self.region,
                config=self._BOTO_CONFIG,
            ),
        )

    async def upload(self, file_content: bytes, key: str) -> None:
        """Upload file content to GCS via simple PUT."""
        try:
            async with await self._get_client() as client:
                await client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=file_content,
                )
        except ClientError as e:
            msg = f"Failed to upload to GCS: {key}"
            raise FileUploadError(msg) from e

    async def download(self, key: str) -> bytes:
        """Download file content from GCS."""
        try:
            async with await self._get_client() as client:
                response = await client.get_object(Bucket=self.bucket_name, Key=key)
                return await response["Body"].read()
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                msg = f"File not found: {key}"
                raise StorageFileNotFoundError(msg) from e
            msg = f"Failed to download from GCS: {key}"
            raise FileDownloadError(msg) from e

    async def get_download_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a presigned download URL using the XML API."""
        try:
            async with await self._get_client() as client:
                return await client.generate_presigned_url(
                    ClientMethod="get_object",
                    Params={"Bucket": self.bucket_name, "Key": key},
                    ExpiresIn=expires_in,
                )
        except ClientError as e:
            msg = f"Failed to generate GCS download URL for key: {key}"
            raise FileDownloadError(msg) from e

    async def delete(self, key: str) -> None:
        """Delete a file from GCS."""
        try:
            async with await self._get_client() as client:
                await client.delete_object(Bucket=self.bucket_name, Key=key)
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                return
            msg = f"Failed to remove GCS object: {key}"
            raise FileDeleteError(msg) from e

    async def create_upload_session(
        self,
        *,
        key: str,
        content_type: str,
        content_length: int | None = None,
    ) -> StorageUploadSession:
        """Create a simple (single PUT) presigned upload URL."""
        del content_length
        try:
            async with await self._get_client() as client:
                upload_url = await client.generate_presigned_url(
                    ClientMethod="put_object",
                    Params={
                        "Bucket": self.bucket_name,
                        "Key": key,
                        "ContentType": content_type,
                    },
                    ExpiresIn=3600,
                )
        except ClientError as e:
            msg = f"Failed to create GCS upload session for key: {key}"
            raise FileUploadError(msg) from e

        return StorageUploadSession(
            upload_url=upload_url,
            method="PUT",
            headers={"Content-Type": content_type},
        )

    # ------------------------------------------------------------------
    #  Multipart-upload helpers (not part of AbstractStorage)
    #  These enable browser-direct parallel chunked uploads.
    # ------------------------------------------------------------------

    async def create_multipart_upload(
        self,
        *,
        key: str,
        content_type: str,
    ) -> str:
        """Initiate an S3-style multipart upload and return the UploadId."""
        try:
            async with await self._get_client() as client:
                response = await client.create_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=key,
                    ContentType=content_type,
                )
                return response["UploadId"]
        except ClientError as e:
            msg = f"Failed to initiate multipart upload for key: {key}"
            raise FileUploadError(msg) from e

    async def generate_presigned_part_url(
        self,
        *,
        key: str,
        upload_id: str,
        part_number: int,
        expires_in: int = 3600,
    ) -> str:
        """Return a presigned URL for uploading a single multipart part."""
        try:
            async with await self._get_client() as client:
                return await client.generate_presigned_url(
                    ClientMethod="upload_part",
                    Params={
                        "Bucket": self.bucket_name,
                        "Key": key,
                        "UploadId": upload_id,
                        "PartNumber": part_number,
                    },
                    ExpiresIn=expires_in,
                )
        except ClientError as e:
            msg = f"Failed to presign part {part_number} for key: {key}"
            raise FileUploadError(msg) from e

    async def complete_multipart_upload(
        self,
        *,
        key: str,
        upload_id: str,
        parts: list[dict[str, object]],
    ) -> dict[str, object]:
        """Complete a multipart upload by assembling the parts.

        Args:
            key: The object key.
            upload_id: The multipart upload session ID.
            parts: Ordered list of {"PartNumber": int, "ETag": str} dicts.

        Returns
        -------
            The response from GCS (contains Location, Bucket, Key, ETag).
        """
        try:
            async with await self._get_client() as client:
                return await client.complete_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=key,
                    UploadId=upload_id,
                    MultipartUpload={"Parts": parts},
                )
        except ClientError as e:
            msg = f"Failed to complete multipart upload for key: {key}"
            raise FileUploadError(msg) from e

    async def abort_multipart_upload(self, *, key: str, upload_id: str) -> None:
        """Abort and clean up a multipart upload session."""
        try:
            async with await self._get_client() as client:
                await client.abort_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=key,
                    UploadId=upload_id,
                )
        except ClientError:
            # If already aborted / does not exist, swallow.
            pass
