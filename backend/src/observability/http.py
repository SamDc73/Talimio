"""HTTP request middleware and route helpers for observability."""

import time
from collections.abc import AsyncIterator
from typing import Any

import structlog
from fastapi import FastAPI, Request
from opentelemetry import trace

from src.config.settings import Settings
from src.observability.event_fields import get_feature_area
from src.observability.log_context import (
    get_log_context,
    reset_log_context,
    set_log_context,
    update_log_context,
)


logger = structlog.get_logger(__name__)


def get_request_route(request: Request) -> str:
    """Resolve the logical route path for the current request."""
    route = request.scope.get("route")
    route_path = getattr(route, "path", None)
    if isinstance(route_path, str) and route_path:
        return route_path
    return request.url.path


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


def _build_request_context(request: Request, route: str) -> dict[str, Any]:
    """Build the request-scoped context used by logging processors."""
    return {
        "route": route,
        "feature_area": get_feature_area(route),
        "course_id": request.path_params.get("course_id") or request.path_params.get("courseId"),
        "content_type": request.path_params.get("content_type") or request.path_params.get("contentType"),
        "session_id": getattr(request.state, "local_session_id", None),
        "model_name": None,
        "status_code": None,
        "error_code": None,
        "user_id": getattr(request.state, "user_id", None),
    }


def _log_completed_request(request: Request, started_at: float, request_context: dict[str, Any]) -> None:
    resolved_route = get_request_route(request)
    status_code = request_context.get("status_code")
    request_context.update(_build_request_context(request, resolved_route))
    request_context["status_code"] = status_code

    latest_context = get_log_context()
    for key, value in latest_context.items():
        if value is None:
            continue
        request_context[key] = value

    duration_ms = round((time.perf_counter() - started_at) * 1000, 2)

    _set_request_span_attributes(
        {
            "app.route": request_context["route"],
            "app.feature_area": request_context["feature_area"],
            "app.request_duration_ms": duration_ms,
            "enduser.id": request_context["user_id"],
            "app.session_id": request_context["session_id"],
            "app.course_id": request_context["course_id"],
            "app.content_type": request_context["content_type"],
        }
    )

    update_log_context(**request_context)
    logger.info(
        "http.request.completed",
        event_name="http.request.completed",
        route=request_context["route"],
        feature_area=request_context["feature_area"],
        status_code=request_context["status_code"],
        user_id=request_context["user_id"],
        session_id=request_context["session_id"],
        course_id=request_context["course_id"],
        content_type=request_context["content_type"],
        duration_ms=duration_ms,
    )


def install_request_context_middleware(app: FastAPI, _settings: Settings) -> None:
    """Install middleware that enriches logs and spans with request context."""
    if getattr(app.state, "request_context_middleware_installed", False):
        return

    @app.middleware("http")
    async def request_context_middleware(request: Request, call_next: Any) -> Any:
        started_at = time.perf_counter()
        initial_route = get_request_route(request)
        request_context = _build_request_context(request, initial_route)
        token = set_log_context(**request_context)
        request_logged = False

        def log_completed_request_once() -> None:
            nonlocal request_logged
            if request_logged:
                return
            request_logged = True
            _log_completed_request(request, started_at, request_context)
            reset_log_context(token)

        try:
            response = await call_next(request)
            request_context["status_code"] = response.status_code
        except Exception:
            log_completed_request_once()
            raise

        body_iterator = getattr(response, "body_iterator", None)
        if body_iterator is None:
            log_completed_request_once()
            return response

        async def log_after_body_stream() -> AsyncIterator[bytes]:
            try:
                async for chunk in body_iterator:
                    yield chunk
            finally:
                log_completed_request_once()

        response.body_iterator = log_after_body_stream()
        return response

    app.state.request_context_middleware_installed = True
