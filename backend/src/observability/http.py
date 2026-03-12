"""HTTP request middleware and route helpers for observability."""

import time
from typing import Any

from fastapi import FastAPI, Request
from opentelemetry import trace

from src.config.settings import Settings


def get_request_route(request: Request) -> str:
    """Resolve the logical route path for the current request."""
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path


def get_feature_area(route: str) -> str:
    """Derive a coarse feature area from /api/v1/<feature>/... paths."""
    parts = [part for part in route.split("/") if part]
    if len(parts) >= 3 and parts[0] == "api" and parts[1] == "v1":
        return parts[2]
    return "app"


def _set_request_span_attributes(attributes: dict[str, Any]) -> None:
    """Attach request-level attributes to the active span when recording."""
    span = trace.get_current_span()
    if not span.is_recording():
        return

    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (bool, int, float, str)):
            span.set_attribute(key, value)
            continue
        span.set_attribute(key, str(value))


def install_request_context_middleware(app: FastAPI, _settings: Settings) -> None:
    """Install middleware that enriches logs and spans with request context."""
    if getattr(app.state, "request_context_middleware_installed", False):
        return

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Any:
        started_at = time.perf_counter()

        try:
            return await call_next(request)
        finally:
            resolved_route = get_request_route(request)
            course_id = request.path_params.get("course_id") or request.path_params.get("courseId")
            user_id = getattr(request.state, "user_id", None)
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            _set_request_span_attributes(
                {
                    "app.route": resolved_route,
                    "app.feature_area": get_feature_area(resolved_route),
                    "app.request_duration_ms": duration_ms,
                    "enduser.id": user_id,
                    "app.course_id": course_id,
                }
            )

    app.state.request_context_middleware_installed = True
