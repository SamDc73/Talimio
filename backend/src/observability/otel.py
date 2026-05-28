"""Runtime setup for OpenTelemetry tracing, metrics, and logs."""

import structlog
from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry._logs import set_logger_provider  # noqa: PLC2701
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter  # noqa: PLC2701
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk._logs import LoggerProvider  # noqa: PLC2701
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor  # noqa: PLC2701
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy.ext.asyncio import AsyncEngine

from src.config.settings import Settings

from .http import install_request_context_middleware
from .resources import build_resource, parse_otlp_headers, resolve_signal_endpoint


logger = structlog.get_logger(__name__)


def configure_observability(app: FastAPI, *, settings: Settings, engine: AsyncEngine) -> None:
    """Configure OpenTelemetry tracing, metrics, and request context enrichment."""
    install_request_context_middleware(app, settings)

    if not settings.otel_enabled:
        logger.debug("observability.otel.disabled")
        return

    headers = parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS)
    traces_endpoint = resolve_signal_endpoint(
        settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
        "v1/traces",
    )
    metrics_endpoint = resolve_signal_endpoint(
        settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT,
        "v1/metrics",
    )
    logs_endpoint = resolve_signal_endpoint(
        settings.OTEL_EXPORTER_OTLP_ENDPOINT,
        settings.OTEL_EXPORTER_OTLP_LOGS_ENDPOINT,
        "v1/logs",
    )

    if not traces_endpoint:
        logger.warning("observability.otel.tracing_endpoint_missing")
        return

    resource = build_resource(settings)
    _configure_traces(
        app,
        traces_endpoint,
        headers=headers,
        resource=resource,
        timeout=settings.OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS,
    )

    if metrics_endpoint:
        _configure_metrics(
            app,
            metrics_endpoint,
            headers=headers,
            resource=resource,
            timeout=settings.OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS,
        )

    if logs_endpoint:
        _configure_logs(
            app,
            logs_endpoint,
            headers=headers,
            resource=resource,
            timeout=settings.OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS,
        )

    if not getattr(app.state, "otel_fastapi_instrumented", False):
        FastAPIInstrumentor.instrument_app(app, excluded_urls="/health")
        app.state.otel_fastapi_instrumented = True

    if not getattr(app.state, "otel_sqlalchemy_instrumented", False):
        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        app.state.otel_sqlalchemy_instrumented = True


def _configure_traces(
    app: FastAPI,
    endpoint: str,
    *,
    headers: dict[str, str],
    resource: Resource,
    timeout: int,
) -> None:
    """Configure the OpenTelemetry tracer provider and exporter once per app."""
    if getattr(app.state, "otel_traces_configured", False):
        return

    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers, timeout=timeout))
    )
    trace.set_tracer_provider(tracer_provider)
    app.state.otel_traces_configured = True
    logger.info(
        "observability.otel.tracing.initialized",
        event_name="observability.otel.tracing.initialized",
        otlp_traces_endpoint=endpoint,
    )


def _configure_metrics(
    app: FastAPI,
    endpoint: str,
    *,
    headers: dict[str, str],
    resource: Resource,
    timeout: int,
) -> None:
    """Configure the OpenTelemetry meter provider and exporter once per app."""
    if getattr(app.state, "otel_metrics_configured", False):
        return

    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, headers=headers, timeout=timeout),
        export_interval_millis=60000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    app.state.otel_metrics_configured = True
    logger.info(
        "observability.otel.metrics.initialized",
        event_name="observability.otel.metrics.initialized",
        otlp_metrics_endpoint=endpoint,
    )


def _configure_logs(
    app: FastAPI,
    endpoint: str,
    *,
    headers: dict[str, str],
    resource: Resource,
    timeout: int,
) -> None:
    """Configure the OpenTelemetry logger provider and attach an OTLP handler to stdlib logging."""
    if getattr(app.state, "otel_logs_configured", False):
        return

    # Local import avoids a circular dependency between src.observability and src.config.logging.
    from src.config.logging import attach_handler_to_named_loggers, build_otlp_log_handler

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(
        BatchLogRecordProcessor(OTLPLogExporter(endpoint=endpoint, headers=headers, timeout=timeout))
    )
    set_logger_provider(logger_provider)

    otlp_handler = build_otlp_log_handler(logger_provider)
    attach_handler_to_named_loggers(otlp_handler)

    app.state.otel_logs_configured = True
    logger.info(
        "observability.otel.logs.initialized",
        event_name="observability.otel.logs.initialized",
        otlp_logs_endpoint=endpoint,
    )
