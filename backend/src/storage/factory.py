"""Storage provider factory for creating the appropriate storage instance."""

from functools import lru_cache

from src.config import get_settings

from .base import AbstractStorage
from .gcs import GCSStorage
from .local import LocalStorage
from .r2 import R2Storage


STORAGE_PROVIDER_LOCAL = "local"
STORAGE_PROVIDER_R2 = "r2"
STORAGE_PROVIDER_GCS = "gcs"


def get_default_storage_provider_name() -> str:
    """Return the normalized provider used for new writes."""
    return get_settings().STORAGE_PROVIDER.lower()


@lru_cache
def get_storage_provider(provider_name: str | None = None) -> AbstractStorage:
    """Get a cached storage provider instance by name.

    Returns
    -------
        Storage provider instance based on configuration

    Note:
        This function is cached to ensure we reuse the same instance
        throughout the application lifecycle.
    """
    settings = get_settings()
    provider = (provider_name or settings.STORAGE_PROVIDER).lower()

    if provider == STORAGE_PROVIDER_LOCAL:
        return LocalStorage(base_path=settings.LOCAL_STORAGE_PATH)

    if provider == STORAGE_PROVIDER_R2:
        if not (settings.R2_ACCOUNT_ID and settings.R2_ACCESS_KEY_ID and settings.R2_SECRET_ACCESS_KEY):
            msg = "R2 storage selected but R2 credentials are incomplete"
            raise RuntimeError(msg)
        return R2Storage(
            account_id=settings.R2_ACCOUNT_ID,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME,
            region=settings.R2_REGION,
        )

    if provider == STORAGE_PROVIDER_GCS:
        if not settings.GCS_BUCKET_NAME:
            msg = "GCS storage selected but GCS_BUCKET_NAME is empty"
            raise RuntimeError(msg)
        return GCSStorage(bucket_name=settings.GCS_BUCKET_NAME)

    msg = f"Unsupported storage provider: {provider}"
    raise RuntimeError(msg)
