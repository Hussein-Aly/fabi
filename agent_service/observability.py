from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)


def setup_observability() -> None:
    endpoint = os.getenv("LANGFUSE_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("LANGFUSE_OTLP_ENDPOINT not set — OTel tracing disabled")
        return

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from openinference.instrumentation.pydantic_ai import PydanticAIInstrumentor

    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    PydanticAIInstrumentor().instrument(tracer_provider=provider)
    logger.info("OTel tracing enabled → %s", endpoint)
