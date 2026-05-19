"""Cost telemetry from RunUsage.

Observational only — emits cost as a `usage.cost` span and a counter
metric. Single-model setup. When more models are added, reintroduce
a `model_name` parameter and a lookup table.
"""

from __future__ import annotations

from opentelemetry import metrics, trace
from pydantic_ai.usage import RunUsage

# Single model in the system. When we add a second, this becomes a lookup.
_MODEL_NAME = "mistral-llm"

# Rates in EUR per 1,000 tokens.
# TODO: replace with company-internal chargeback rates when defined.
_INPUT_PER_1K_EUR = 0.002
_OUTPUT_PER_1K_EUR = 0.006

_tracer = trace.get_tracer(__name__)
_meter = metrics.get_meter(__name__)
_cost_counter = _meter.create_counter(
    name="llm.cost.eur",
    description="LLM cost per agent run, in EUR",
    unit="EUR",
)


def compute_cost_eur(usage: RunUsage) -> float:
    """Multiply token counts by the configured rates."""
    input_cost = (usage.input_tokens / 1000) * _INPUT_PER_1K_EUR
    output_cost = (usage.output_tokens / 1000) * _OUTPUT_PER_1K_EUR
    return round(input_cost + output_cost, 6)


def emit_cost_telemetry(usage: RunUsage) -> None:
    """Emit cost as a dedicated `usage.cost` span plus a counter metric."""
    cost_eur = compute_cost_eur(usage)

    with _tracer.start_as_current_span("usage.cost") as span:
        span.set_attribute("cost.eur", cost_eur)
        span.set_attribute("tokens.input", usage.input_tokens)
        span.set_attribute("tokens.output", usage.output_tokens)
        span.set_attribute("tokens.total", usage.total_tokens)
        span.set_attribute("model.name", _MODEL_NAME)

    _cost_counter.add(cost_eur, attributes={"model": _MODEL_NAME})