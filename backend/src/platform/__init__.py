"""Platform-specific features for cloud deployment.

This module contains endpoints and functionality that are only available
in the cloud SaaS deployment, not in the self-hosted version.
"""

from fastapi import APIRouter

from src.config.settings import get_settings


# Main platform router
platform_router = APIRouter(prefix="/api/v1/platform", tags=["platform"])

# Only include platform routes if running in cloud mode
settings = get_settings()
if settings.PLATFORM_MODE == "cloud":
    from .admin import admin_router
    from .analytics import analytics_router
    from .billing import billing_router
    from .limits import limits_router

    platform_router.include_router(billing_router, prefix="/billing", tags=["billing"])
    platform_router.include_router(limits_router, prefix="/limits", tags=["limits"])
    platform_router.include_router(analytics_router, prefix="/analytics", tags=["analytics"])
    platform_router.include_router(admin_router, prefix="/admin", tags=["admin"])
else:
    # In OSS mode, return a simple message
    @platform_router.get("/")
    async def platform_info():
        return {
            "message": "Platform features are not available in self-hosted mode",
            "mode": "oss",
            "upgrade_url": "https://talimio.com/pricing",
        }
