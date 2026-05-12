"""Google Cloud Storage implementation."""

from datetime import timedelta

import google.auth
from google.api_core.exceptions import GoogleAPIError, NotFound
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.cloud import storage
from starlette.concurrency import run_in_threadpool

from .base import AbstractStorage, StorageUploadSession
from .exceptions import FileDeleteError, FileDownloadError, FileUploadError, StorageFileNotFoundError


_GCS_SCOPES = ("https://www.googleapis.com/auth/cloud-platform",)


class GCSStorage(AbstractStorage):
    """Google Cloud Storage provider using the official Python client."""

    def __init__(self, *, bucket_name: str) -> None:
        self.bucket_name = bucket_name
        credentials, project_id = google.auth.default(scopes=_GCS_SCOPES)
        self._client = storage.Client(project=project_id, credentials=credentials)
        self._bucket = self._client.bucket(bucket_name)

    async def upload(self, file_content: bytes, key: str) -> None:
        """Upload file content to GCS."""
        blob = self._bucket.blob(key)
        try:
            await run_in_threadpool(blob.upload_from_string, file_content)
        except GoogleAPIError as error:
            msg = f"Failed to upload to GCS: {key}"
            raise FileUploadError(msg) from error

    async def download(self, key: str) -> bytes:
        """Download file content from GCS."""
        blob = self._bucket.blob(key)
        try:
            return await run_in_threadpool(blob.download_as_bytes)
        except NotFound as error:
            msg = f"File not found: {key}"
            raise StorageFileNotFoundError(msg) from error
        except GoogleAPIError as error:
            msg = f"Failed to download from GCS: {key}"
            raise FileDownloadError(msg) from error

    async def get_download_url(self, key: str) -> str:
        """Return a V4 signed GCS download URL."""
        blob = self._bucket.blob(key)
        try:
            service_account_email, access_token = await self._get_signing_identity()
            return await run_in_threadpool(
                blob.generate_signed_url,
                version="v4",
                expiration=timedelta(hours=1),
                method="GET",
                service_account_email=service_account_email,
                access_token=access_token,
            )
        except GoogleAuthError as error:
            msg = f"Failed to generate GCS signed URL for key: {key}"
            raise FileDownloadError(msg) from error

    async def _get_signing_identity(self) -> tuple[str, str]:
        """Return IAM signing inputs for Cloud Run service account URLs."""
        credentials = getattr(self._client, "_credentials", None)
        if credentials is None:
            msg = "GCS signed URLs require application credentials"
            raise FileDownloadError(msg)

        if not credentials.valid:
            await run_in_threadpool(credentials.refresh, GoogleAuthRequest())

        service_account_email = getattr(credentials, "service_account_email", None)
        access_token = getattr(credentials, "token", None)
        if not service_account_email or not access_token:
            msg = "GCS signed URLs require service account credentials"
            raise FileDownloadError(msg)

        return service_account_email, access_token

    async def delete(self, key: str) -> None:
        """Delete a file from GCS."""
        blob = self._bucket.blob(key)
        try:
            await run_in_threadpool(blob.delete)
        except NotFound:
            return
        except GoogleAPIError as error:
            msg = f"Failed to remove GCS object: {key}"
            raise FileDeleteError(msg) from error

    async def create_upload_session(
        self,
        *,
        key: str,
        content_type: str,
        content_length: int | None = None,  # noqa: ARG002
    ) -> StorageUploadSession:
        """Create a GCS direct upload signed URL."""
        # Note: content_length is intentionally ignored for GCS signed URLs
        # as GCS does not require it for v4 PUT signatures, unlike S3.
        blob = self._bucket.blob(key)
        try:
            service_account_email, access_token = await self._get_signing_identity()
            upload_url = await run_in_threadpool(
                blob.generate_signed_url,
                version="v4",
                expiration=timedelta(hours=1),
                method="PUT",
                content_type=content_type,
                service_account_email=service_account_email,
                access_token=access_token,
            )
        except (GoogleAPIError, GoogleAuthError) as error:
            msg = f"Failed to create GCS upload session for key: {key}"
            raise FileUploadError(msg) from error

        return StorageUploadSession(upload_url=upload_url, method="PUT")
