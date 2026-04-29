"""HTTP request middleware and route helpers for observability."""

import time
from typing import Any

import structlog
from fastapi import FastAPI, Request
from opentelemetry import trace
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.auth.request_state import get_local_session_id_from_state, get_user_id_from_state
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
        "session_id": get_local_session_id_from_state(request),
        "model_name": None,
        "status_code": None,
        "error_code": None,
        "user_id": get_user_id_from_state(request),
    }


def _log_completed_request(request: Request, started_at: float, request_context: dict[str, Any]) -> None:
    resolved_route = get_request_route(request)
    status_code = request_context.get("status_code")

    latest_context = get_log_context()
    for key, value in latest_context.items():
        if value is None:
            continue
        request_context[key] = value

    resolved_context = _build_request_context(request, resolved_route)
    for key, value in resolved_context.items():
        if value is None:
            continue
        request_context[key] = value
    request_context["status_code"] = status_code

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


class RequestContextMiddleware:
    """Pure ASGI middleware for request-scoped logging and span context."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Set request log context and finalize it from ASGI response events."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
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

        async def send_with_request_context(message: Message) -> None:
            if message["type"] == "http.response.start":
                request_context["status_code"] = message["status"]

            try:
                await send(message)
            finally:
                if message["type"] == "http.response.body" and not message.get("more_body", False):
                    log_completed_request_once()

        try:
            await self.app(scope, receive, send_with_request_context)
        except Exception:
            log_completed_request_once()
            raise
        finally:
            log_completed_request_once()
            reset_log_context(token)


def install_request_context_middleware(app: FastAPI, _settings: Settings) -> None:
    """Install middleware that enriches logs and spans with request context."""
    if getattr(app.state, "request_context_middleware_installed", False):
        return

    app.add_middleware(RequestContextMiddleware)
    app.state.request_context_middleware_installed = True
