"""Auth configuration validator to prevent frontend/backend mismatches."""

import logging
from typing import Any

from src.config.settings import get_settings


logger = logging.getLogger(__name__)


class AuthConfigurationError(Exception):
    """Exception raised when auth configuration is invalid or inconsistent."""


class AuthConfigValidator:
    """Validates authentication configuration consistency."""

    @staticmethod
    def validate_backend_config() -> dict[str, Any]:
        """Validate backend authentication configuration.

        Returns
        -------
            Dict with validation results and recommendations
        """
        settings = get_settings()
        issues = []
        warnings = []

        # Check AUTH_PROVIDER setting
        auth_provider = settings.AUTH_PROVIDER.lower()

        if auth_provider not in ["none", "supabase"]:
            issues.append(f"Invalid AUTH_PROVIDER: {auth_provider}. Must be 'none' or 'supabase'")

        # Validate Supabase configuration if enabled
        if auth_provider == "supabase":
            supabase_url = settings.SUPABASE_URL
            supabase_publishable = settings.SUPABASE_PUBLISHABLE_KEY

            if not supabase_url:
                issues.append("SUPABASE_URL is required when AUTH_PROVIDER=supabase")
            elif not supabase_url.startswith("https://"):
                issues.append("SUPABASE_URL must start with https://")

            if not supabase_publishable:
                issues.append("SUPABASE_PUBLISHABLE_KEY is required when AUTH_PROVIDER=supabase")
            elif not supabase_publishable.startswith("sb_publishable_"):
                warnings.append("SUPABASE_PUBLISHABLE_KEY should start with 'sb_publishable_'")

        # Check SECRET_KEY for session management
        secret_key = settings.SECRET_KEY
        if not secret_key:
            issues.append("SECRET_KEY is required for session management")
        elif secret_key == "your-secret-key-change-in-production-auth-sessions-development":  # noqa: S105
            if settings.ENVIRONMENT == "production":
                issues.append("SECRET_KEY must be changed in production")
            else:
                warnings.append("SECRET_KEY should be changed from default value")

        return {
            "valid": len(issues) == 0,
            "auth_provider": auth_provider,
            "issues": issues,
            "warnings": warnings,
            "recommendations": AuthConfigValidator._get_recommendations(auth_provider, issues, warnings),
        }

    @staticmethod
    def _get_recommendations(auth_provider: str, issues: list[str], warnings: list[str]) -> list[str]:
        """Generate configuration recommendations."""
        recommendations = []

        if auth_provider == "supabase" and issues:
            recommendations.append("To fix Supabase configuration:")
            recommendations.append("1. Set SUPABASE_URL to your Supabase project URL")
            recommendations.append("2. Set SUPABASE_PUBLISHABLE_KEY (anon/publishable key)")
            recommendations.append("3. Ensure the frontend can reach the backend and send cookies (httpOnly session)")

        if auth_provider == "none" and not issues:
            recommendations.append("Single-user mode active:")
            recommendations.append("1. No login/signup functionality will be available")
            recommendations.append("2. Default user will be used for all operations")

        if warnings:
            recommendations.append("Address warnings for better security:")
            recommendations.extend(f"- {warning}" for warning in warnings)

        return recommendations

    @staticmethod
    def validate_and_log() -> None:
        """Validate configuration and log results."""
        try:
            result = AuthConfigValidator.validate_backend_config()

            if result["valid"]:
                logger.info(f"✅ Auth configuration valid (provider: {result['auth_provider']})")

                if result["warnings"]:
                    logger.warning("⚠️  Configuration warnings:")
                    for warning in result["warnings"]:
                        logger.warning(f"   - {warning}")

                if result["recommendations"]:
                    logger.info("💡 Configuration recommendations:")
                    for rec in result["recommendations"]:
                        logger.info(f"   {rec}")
            else:
                logger.error("❌ Auth configuration invalid!")
                logger.error("Issues found:")
                for issue in result["issues"]:
                    logger.error(f"   - {issue}")

                if result["recommendations"]:
                    logger.info("💡 How to fix:")
                    for rec in result["recommendations"]:
                        logger.info(f"   {rec}")

                msg = f"Invalid auth configuration: {'; '.join(result['issues'])}"
                raise AuthConfigurationError(msg)

        except Exception as e:
            logger.exception(f"Failed to validate auth configuration: {e}")
            raise

    @staticmethod
    def check_frontend_backend_compatibility() -> dict[str, Any]:
        """Check for common frontend/backend auth mismatches.

        Note: This checks based on typical patterns and environment variables.
        """
        settings = get_settings()
        backend_auth = settings.AUTH_PROVIDER.lower()

        # Common mismatch patterns
        potential_issues = []

        if backend_auth == "none":
            potential_issues.append(
                {
                    "type": "mismatch_warning",
                    "message": "Backend in single-user mode (AUTH_PROVIDER=none)",
                    "recommendation": "No frontend auth flag needed; /api/v1/auth/me returns the demo user",
                }
            )

        if backend_auth == "supabase":
            supabase_url = settings.SUPABASE_URL
            if supabase_url:
                potential_issues.append(
                    {
                        "type": "mismatch_warning",
                        "message": "Backend in multi-user mode (AUTH_PROVIDER=supabase)",
                        "recommendation": f"Ensure frontend points at this backend and cookies are allowed (SUPABASE_URL={supabase_url})",
                    }
                )

        return {"backend_auth_provider": backend_auth, "potential_issues": potential_issues, "timestamp": "2025-07-28"}


def validate_auth_on_startup() -> None:
    """Entry point for startup auth validation."""
    logger.info("🔐 Validating authentication configuration...")

    try:
        # Validate backend config
        AuthConfigValidator.validate_and_log()

        # Check for potential frontend/backend mismatches
        compatibility = AuthConfigValidator.check_frontend_backend_compatibility()

        if compatibility["potential_issues"]:
            logger.info("🔍 Frontend/Backend compatibility check:")
            for issue in compatibility["potential_issues"]:
                if issue["type"] == "mismatch_warning":
                    logger.info(f"   i  {issue['message']}")  # Using 'i' instead of information symbol to avoid RUF001
                    logger.info(f"   💡 {issue['recommendation']}")

        logger.info("✅ Auth configuration validation complete")

    except AuthConfigurationError:
        logger.exception("❌ Startup halted due to auth configuration errors")
        raise
    except Exception as e:
        logger.exception(f"❌ Unexpected error during auth validation: {e}")
        raise
