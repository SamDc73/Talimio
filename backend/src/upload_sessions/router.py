"""Upload session router for provider-agnostic direct file uploads."""

import uuid

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from src.auth import CurrentAuth
from src.config.schema_casing import build_camel_config
from src.storage.exceptions import FileUploadError
from src.storage.factory import get_default_storage_provider_name, get_storage_provider


router = APIRouter(prefix="/api/v1/upload-sessions", tags=["upload-sessions"])


class UploadSessionRequest(BaseModel):
    """Request a direct upload session for a file."""

    model_config = build_camel_config()

    filename: str
    content_type: str
    file_size: int | None = None


class UploadSessionResponse(BaseModel):
    """Provider-issued direct upload session details."""

    model_config = build_camel_config()

    upload_url: str
    method: str
    headers: dict[str, str] = Field(default_factory=dict)
    file_path: str
    storage_provider: str


@router.post("")
async def create_upload_session(
    payload: UploadSessionRequest,
    auth: CurrentAuth,
) -> UploadSessionResponse:
    """Create a provider-specific direct upload session."""
    file_extension = payload.filename.lower().split(".")[-1]
    if file_extension not in {"epub", "pdf"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF and EPUB files are supported",
        )

    storage_provider = get_default_storage_provider_name()
    storage_key = f"books/{auth.user_id!s}/direct/{uuid.uuid4()}-{payload.filename}"
    storage = get_storage_provider(storage_provider)
    try:
        session = await storage.create_upload_session(
            key=storage_key,
            content_type=payload.content_type,
            content_length=payload.file_size,
        )
    except FileUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return UploadSessionResponse(
        upload_url=session.upload_url,
        method=session.method,
        headers=session.headers,
        file_path=storage_key,
        storage_provider=storage_provider,
    )


@router.put("/local/{key:path}", include_in_schema=False)
async def write_local_upload(key: str, request: Request, auth: CurrentAuth) -> Response:
    """Receive raw bytes for self-hosted local-storage uploads.

    Mirrors what cloud providers do via presigned URLs: the frontend PUTs the
    file body straight to the URL returned by ``create_upload_session``. For
    local storage that URL is same-origin and points here. We scope writes to
    the caller's ``books/{user_id}/direct/`` prefix to match the validation
    that ``create_book_from_existing_storage`` performs on finalize.
    """
    expected_prefix = f"books/{auth.user_id!s}/direct/"
    if not key.startswith(expected_prefix):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Path not owned by user",
        )

    storage = get_storage_provider("local")
    try:
        await storage.upload(await request.body(), key)
    except FileUploadError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)
