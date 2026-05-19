"""Usage telemetry pipeline.

Observational only — emits cost and token telemetry after each agent
run. No enforcement, no blocking, no state.
"""

from __future__ import annotations

import logging

from pydantic_ai import AgentRunResult

from mbai.ai_gateway.usage.cost import emit_cost_telemetry

logger = logging.getLogger(__name__)


async def run_usage_pipeline(result: AgentRunResult) -> None:
    """Emit usage telemetry from an agent run. Never raises."""
    try:
        emit_cost_telemetry(result.usage())
    except Exception:
        logger.exception("usage telemetry emission failed")