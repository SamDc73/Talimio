import pytest
from fastapi import status

from src.main import app


pytestmark = pytest.mark.integration


class _RecordingSpan:
    def __init__(self) -> None:
        self.attributes: dict[str, object] = {}

    def is_recording(self) -> bool:
        return True

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


@pytest.mark.asyncio
async def test_observability_middleware_is_installed() -> None:
    assert getattr(app.state, "request_context_middleware_installed", False) is True


@pytest.mark.asyncio
async def test_observability_sets_span_attributes_for_api_route(client, monkeypatch) -> None:
    from src.observability import http as observability_http

    span = _RecordingSpan()
    monkeypatch.setattr(observability_http.trace, "get_current_span", lambda: span)

    course_id = "00000000-0000-0000-0000-000000000999"
    response = await client.get(f"/api/v1/courses/{course_id}")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert span.attributes.get("app.feature_area") == "courses"
    assert str(span.attributes.get("app.route", "")).startswith("/api/v1/courses")
    assert span.attributes.get("app.course_id") == course_id
    assert "http.response.status_code" not in span.attributes
    assert "deployment.environment" not in span.attributes
    assert "service.version" not in span.attributes
    assert "app.request_duration_ms" in span.attributes


@pytest.mark.asyncio
async def test_observability_sets_span_attributes_for_non_api_route(client, monkeypatch) -> None:
    from src.observability import http as observability_http

    span = _RecordingSpan()
    monkeypatch.setattr(observability_http.trace, "get_current_span", lambda: span)

    response = await client.get("/health")

    assert response.status_code == status.HTTP_200_OK
    assert span.attributes.get("app.feature_area") == "app"
    assert span.attributes.get("app.route") == "/health"
    assert "http.response.status_code" not in span.attributes
