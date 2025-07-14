"""Storage provider factory for creating the appropriate storage instance."""

from functools import lru_cache

from src.config import get_settings

from .base import AbstractStorage
from .local import LocalStorage
from .r2 import R2Storage


@lru_cache
def get_storage_provider() -> AbstractStorage:
    """Get the configured storage provider instance.

    Returns
    -------
        Storage provider instance based on configuration

    Note:
        This function is cached to ensure we reuse the same instance
        throughout the application lifecycle.
    """
    settings = get_settings()

    # Check if R2 is configured and should be used
    if (
        settings.STORAGE_PROVIDER == "r2"
        and settings.R2_ACCOUNT_ID
        and settings.R2_ACCESS_KEY_ID
        and settings.R2_SECRET_ACCESS_KEY
    ):
        return R2Storage(
            account_id=settings.R2_ACCOUNT_ID,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            bucket_name=settings.R2_BUCKET_NAME,
            region=settings.R2_REGION,
        )

    # Default to local storage
    return LocalStorage(base_path=settings.LOCAL_STORAGE_PATH)
