"""OpenTelemetry SDK setup.

Called once at app startup from FastAPI's lifespan. Configures the
TracerProvider with an exporter chosen by settings.otel_exporter:

- "jsonl" (default): spans appended to a JSONL file (one span per line).
                     Local dev, tests, and any environment without a
                     remote trace backend.
- "console":         spans dumped to stdout. One-off debugging only;
                     pretty-printed, not JSONL.
- "langfuse":        spans sent to the demo Langfuse server via the
                     Langfuse SDK's OTel bridge. Production / demo.

Metrics are always written to a JSONL file regardless of trace mode
— Langfuse doesn't ingest OTel metrics. When the corporate OTel
endpoint lands in Q2/Q3, add a fourth mode "otlp" that uses
OTLPSpanExporter + OTLPMetricExporter pointed at the corp endpoint.
The rest of the codebase will not change.

Lenient on failure: logs a warning and continues. The app stays up
even if telemetry init fails — observability degrades, app does not.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from mbai.telemetry.logging_config import configure_logging

from mbai.aiserver.config import settings
from mbai.telemetry.exporters import JsonlFileSpanExporter
from mbai.telemetry.exporters import JsonlFileMetricExporter

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger(__name__)

# Module-level state: whether telemetry was successfully initialized.
# Currently unused by other modules (Agent.instrument_all() handles
# per-agent enablement globally) but kept as a future-useful signal —
# e.g. a /health-check endpoint could report telemetry health.
_instrumentation_active: bool = False

# Hardcoded for Q1 — moves to settings later.
# TODO(post-Q1): pull these from aiserver/config.py settings.
_LANGFUSE_PUBLIC_KEY = "pk-lf-3b152d69-1138-41fb-a874-fde20c47af27"
_LANGFUSE_SECRET_KEY = "sk-lf-68dde749-461c-4fd4-a45a-4d507980cb09"
_LANGFUSE_BASE_URL = "http://fabidemoclouddevel.sq.fabasoft.com:3000"


def configure_telemetry(app: "FastAPI", service_name: str = "fabi-aiserver") -> None:
    """Initialize OTel for the whole app. Call once at startup.

    Args:
        app: the FastAPI app instance — needed for FastAPIInstrumentor.
        service_name: identifies this service in trace exports.
    """
    global _instrumentation_active

    configure_logging()

    mode = settings.otel_exporter.lower()

    try:
        # --- Traces ---
        if mode == "langfuse":
            _configure_langfuse_mode(service_name)
        elif mode == "console":
            _configure_console_mode(service_name)
        elif mode == "jsonl":
            _configure_jsonl_mode(service_name)
        else:
            logger.warning("Unknown otel_exporter=%r — falling back to jsonl", mode)
            _configure_jsonl_mode(service_name)

        # --- Metrics (always JSONL until corp endpoint exists) ---
        _configure_metrics(service_name)

        # --- HTTP layer auto-instrumentation ---
        _instrument_http_layer(app)

        # --- Pydantic AI instrumentation, globally ---
        # One switch for every Agent constructed from here on. Equivalent
        # to passing instrument=True to each Agent individually, but
        # without threading a flag through agent_service.
        _enable_pydantic_ai_instrumentation()

        _instrumentation_active = True
        logger.info("Telemetry initialized: traces=%s, metrics=jsonl", mode)

    except Exception as e:
        logger.warning(
            "Telemetry initialization failed (%s) — continuing without spans. " "App functionality is unaffected.",
            e,
        )
        _instrumentation_active = False


def instrumentation_active() -> bool:
    """Return True if telemetry was successfully initialized.

    No longer required by other modules — kept for future use
    (health checks, conditional debug logging, etc.).
    """
    return _instrumentation_active


def _configure_jsonl_mode(service_name: str) -> None:
    """Spans → JSONL file. One span per line, append-only.

    Drops ASGI streaming sub-spans (`http send`, `http receive`) — these
    fire once per SSE chunk in streaming responses and would otherwise
    flood the file. The substantive spans (POST, agent.run, guardrails.*,
    tool calls) pass through unchanged.
    """
    from mbai.telemetry.exporters import FilteringSpanExporter

    inner = JsonlFileSpanExporter(settings.otel_jsonl_path)
    exporter = FilteringSpanExporter(
        inner,
        exclude_patterns=[r" http (send|receive)$"],
    )

    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)


def _configure_console_mode(service_name: str) -> None:
    """Spans → stdout (pretty-printed, multi-line). Debugging only."""
    resource = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


def _configure_langfuse_mode(service_name: str) -> None:
    """Spans → Langfuse via its SDK's OTel bridge.

    Langfuse v3 hooks into the global TracerProvider; once initialized,
    any span emitted via the OTel API is captured and forwarded to the
    Langfuse backend. Pydantic AI is the primary span producer
    (enabled by `_enable_pydantic_ai_instrumentation` further below).
    """
    import os

    os.environ["LANGFUSE_PUBLIC_KEY"] = _LANGFUSE_PUBLIC_KEY
    os.environ["LANGFUSE_SECRET_KEY"] = _LANGFUSE_SECRET_KEY
    os.environ["LANGFUSE_BASE_URL"] = _LANGFUSE_BASE_URL

    # Lazy import: only required in langfuse mode, so other modes
    # don't need the package importable.
    from langfuse import get_client

    client = get_client()
    if not client.auth_check():
        raise RuntimeError(f"Langfuse authentication failed against {_LANGFUSE_BASE_URL}")


def _configure_metrics(service_name: str) -> None:
    """Metrics → JSONL file, always. Independent of trace mode because
    Langfuse doesn't ingest OTel metrics — only traces. When corp OTel
    lands, metrics get a real exporter alongside traces.
    """

    resource = Resource.create({"service.name": service_name})
    reader = PeriodicExportingMetricReader(
        JsonlFileMetricExporter(settings.otel_metrics_jsonl_path),
        export_interval_millis=settings.otel_metric_export_interval_ms,
    )
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(provider)


def _instrument_http_layer(app: "FastAPI") -> None:
    """Auto-instrument FastAPI routes and outbound HTTPX calls.

    Produces spans for incoming HTTP requests and outbound LLM calls
    automatically — no decorators or manual span code needed in routes.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    HTTPXClientInstrumentor().instrument()


def instrument_fastapi(app: "FastAPI") -> None:
    """Apply FastAPI auto-instrumentation.

    Call from api_server.py immediately after `app = FastAPI(...)`,
    not inside lifespan — middleware attachment from lifespan is
    unreliable across versions of opentelemetry-instrumentation-fastapi.
    """
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def _enable_pydantic_ai_instrumentation() -> None:
    """Turn on OTel instrumentation for every Agent created globally.

    Equivalent to constructing each Agent with `instrument=True`, but
    centralized so agent_service code doesn't need a flag threaded
    through it. Works in any trace mode (jsonl, console, langfuse) —
    spans flow to whatever TracerProvider was set above.
    """
    from pydantic_ai import Agent

    Agent.instrument_all()
