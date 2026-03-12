"""Helpers for OTLP headers, endpoints, and resource attributes."""

from opentelemetry.sdk.resources import Resource

from src.config.settings import Settings


_SERVICE_NAME = "api"
_SERVICE_NAMESPACE = "talimio"
_DEFAULT_RELEASE_VERSION = "0.1.0"


def parse_otlp_headers(raw_headers: str) -> dict[str, str]:
    """Parse comma-delimited OTLP headers from settings."""
    headers: dict[str, str] = {}
    for item in raw_headers.split(","):
        header = item.strip()
        if not header or "=" not in header:
            continue
        key, value = header.split("=", 1)
        key_text = key.strip()
        value_text = value.strip()
        if key_text and value_text:
            headers[key_text] = value_text
    return headers


def resolve_signal_endpoint(base_endpoint: str, configured_endpoint: str, suffix: str) -> str:
    """Resolve a signal endpoint from either a direct URL or a shared OTLP base URL."""
    configured = configured_endpoint.strip()
    if configured:
        return configured

    base = base_endpoint.strip().rstrip("/")
    if not base:
        return ""

    if base.endswith(suffix):
        return base

    return f"{base}/{suffix}"


def resolve_release_version(settings: Settings) -> str:
    """Return the release label attached to telemetry."""
    configured = settings.RELEASE_VERSION.strip()
    if configured:
        return configured

    cloud_run_revision = settings.K_REVISION.strip()
    if cloud_run_revision:
        return cloud_run_revision

    return _DEFAULT_RELEASE_VERSION


def build_resource(settings: Settings) -> Resource:
    """Build the shared OpenTelemetry resource from settings."""
    attributes: dict[str, str] = {
        "service.name": _SERVICE_NAME,
        "service.namespace": _SERVICE_NAMESPACE,
        "service.version": resolve_release_version(settings),
        "deployment.environment": settings.ENVIRONMENT,
    }

    for item in settings.OTEL_RESOURCE_ATTRIBUTES.split(","):
        attribute = item.strip()
        if not attribute or "=" not in attribute:
            continue
        key, value = attribute.split("=", 1)
        key_text = key.strip()
        value_text = value.strip()
        if key_text and value_text:
            attributes[key_text] = value_text

    return Resource.create(attributes)
