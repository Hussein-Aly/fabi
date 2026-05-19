"""AI Gateway service.

The single boundary every request passes through on its way to and from
the agent. Composes the gateway sub-features (guardrails, usage) so the
HTTP layer sees only two methods — `pre_run` and `post_run` — rather
than reaching into the pipelines directly.

Stateless and reusable. Constructed once at app startup in the FastAPI
lifespan; the same instance handles all requests concurrently.
Configuration (which checks are active, etc.) is passed at construction
and immutable afterwards.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from pydantic_ai import AgentRunResult

from mbai.ai_gateway.guardrails.base import Check, GuardrailBlocked
from mbai.ai_gateway.guardrails.input import default_input_checks
from mbai.ai_gateway.guardrails.output import default_output_checks
from mbai.ai_gateway.guardrails.pipeline import (
    run_input_pipeline,
    run_output_pipeline,
)
from mbai.ai_gateway.usage.pipeline import run_usage_pipeline
from mbai.ai_gateway.utils.chat_utils import _find_last_user_message_index

logger = logging.getLogger(__name__)


@dataclass
class PreRunOutcome:
    """Outcome of input-side gateway processing.

    `blocked=False` → continue with the (possibly mutated) request body.
    `blocked=True`  → don't run the real agent; emit `refusal_text`
                      via the refusal-agent dispatch path.
    """
    blocked: bool
    refusal_text: str | None = None


class AIGateway:
    """The boundary every request passes through.

    Composes guardrails and usage telemetry. HTTP/protocol callers
    see only `pre_run` and `post_run` and don't know which checks are
    active, which telemetry fires, or what redaction happened.

    Checks are passed at construction so the gateway is configurable
    in tests:

        gateway = AIGateway(input_checks=[LengthCap(max_chars=10)])
    """

    def __init__(
        self,
        input_checks: list[Check] | None = None,
        output_checks: list[Check] | None = None,
    ) -> None:
        self._input_checks = (
            input_checks if input_checks is not None else default_input_checks()
        )
        self._output_checks = (
            output_checks if output_checks is not None else default_output_checks()
        )

    async def pre_run(self, request_body: dict) -> PreRunOutcome:
        """Input-side gateway processing.

        Extracts the latest user message, runs input guardrails on its
        text. If checks redact, mutates `request_body` in place so the
        agent sees the cleaned version. Returns the outcome explicitly
        rather than raising — callers get a single decision point.
        """
        user_idx = _find_last_user_message_index(request_body)
        if user_idx is None:
            # Nothing to check (e.g. only system or assistant messages).
            return PreRunOutcome(blocked=False)

        original = request_body["messages"][user_idx]["content"]

        try:
            result = await run_input_pipeline(
                text=original,
                checks=self._input_checks,
            )
        except GuardrailBlocked as e:
            return PreRunOutcome(
                blocked=True,
                refusal_text=f"I can't process this request. Reason: {e.reason}",
            )

        # Apply redactions in place so the agent sees the cleaned text.
        if result.text != original:
            request_body["messages"][user_idx]["content"] = result.text

        return PreRunOutcome(blocked=False)

    async def post_run(
        self,
        result: AgentRunResult,
        model_name: str,
    ) -> None:
        """Output-side gateway processing.

        Emits usage telemetry (cost, tokens) and runs output guardrails
        (detection-only on streaming surfaces). Never raises — gateway
        failures must not break user responses.
        """
        try:
            await run_usage_pipeline(result, model_name)
        except Exception:
            logger.exception("usage pipeline failed")

        try:
            final_text = (
                result.output if isinstance(result.output, str) else None
            )
            if final_text:
                await run_output_pipeline(final_text, self._output_checks)
        except Exception:
            logger.exception("output guardrails pipeline failed")