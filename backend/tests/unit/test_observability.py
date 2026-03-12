from src.config.settings import Settings
from src.observability.http import get_feature_area
from src.observability.resources import (
    build_resource,
    parse_otlp_headers,
    resolve_release_version,
    resolve_signal_endpoint,
)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "AUTH_SECRET_KEY": "test-secret",
        "ENVIRONMENT": "test",
        "RELEASE_VERSION": "",
        "K_REVISION": "",
        "OTEL_RESOURCE_ATTRIBUTES": "",
    }
    base.update(overrides)
    return Settings(**base)


def test_parse_otlp_headers_ignores_invalid_entries() -> None:
    headers = parse_otlp_headers(" Authorization=Bearer token, invalid, x-scope=alpha, empty= ")

    assert headers == {
        "Authorization": "Bearer token",
        "x-scope": "alpha",
    }


def test_resolve_signal_endpoint_uses_configured_then_base_then_empty() -> None:
    assert resolve_signal_endpoint("https://otel.example.com", "https://custom.example.com/v1/traces", "v1/traces") == (
        "https://custom.example.com/v1/traces"
    )
    assert resolve_signal_endpoint("https://otel.example.com", "", "v1/traces") == "https://otel.example.com/v1/traces"
    assert resolve_signal_endpoint("", "", "v1/traces") == ""


def test_resolve_release_version_precedence() -> None:
    assert resolve_release_version(_settings(RELEASE_VERSION="1.2.3", K_REVISION="rev-9")) == "1.2.3"
    assert resolve_release_version(_settings(RELEASE_VERSION="", K_REVISION="rev-9")) == "rev-9"
    assert resolve_release_version(_settings(RELEASE_VERSION="", K_REVISION="")) == "0.1.0"


def test_build_resource_includes_core_and_custom_attributes() -> None:
    resource = build_resource(
        _settings(
            ENVIRONMENT="staging",
            RELEASE_VERSION="2.0.0",
            OTEL_RESOURCE_ATTRIBUTES="cloud.provider=gcp,cloud.region=us-central1",
        )
    )

    attributes = resource.attributes
    assert attributes["service.name"] == "api"
    assert attributes["service.namespace"] == "talimio"
    assert attributes["service.version"] == "2.0.0"
    assert attributes["deployment.environment"] == "staging"
    assert attributes["cloud.provider"] == "gcp"
    assert attributes["cloud.region"] == "us-central1"


def test_get_feature_area_derives_api_and_fallbacks_for_other_routes() -> None:
    assert get_feature_area("/api/v1/courses/123") == "courses"
    assert get_feature_area("/health") == "app"
