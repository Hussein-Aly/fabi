"""Run lists of guardrail checks under a single OTel span.

Two public functions:
- `run_input_pipeline`:  blocking allowed, redactions modify text
- `run_output_pipeline`: detection only (streaming output cannot be
                         un-sent), no blocking, redactions ignored

Each check runs as a child span so guardrail decisions are visible
in traces alongside the agent run.
"""

from __future__ import annotations

import logging
from typing import Sequence

from opentelemetry import trace

from mbai.ai_gateway.guardrails.base import (
    Check,
    CheckResult,
    GuardrailBlocked,
    GuardrailResult,
)

logger = logging.getLogger(__name__)
_tracer = trace.get_tracer(__name__)


async def run_input_pipeline(
    text: str,
    checks: Sequence[Check],
) -> GuardrailResult:
    """Run input checks. May redact text. Raises GuardrailBlocked on block.

    Checks run in order. A check that redacts produces text that the
    next check sees — order matters if checks interact.
    """
    return await _run_pipeline(
        text=text,
        checks=checks,
        span_name="guardrails.input",
        allow_block=True,
        allow_redact=True,
    )


async def run_output_pipeline(
    text: str,
    checks: Sequence[Check],
) -> GuardrailResult:
    """Run output checks. Detection only — no blocking, no text changes.

    Output guardrails on streaming AG-UI cannot block (tokens have
    already been sent to the user by the time the run completes).
    Violations are recorded on spans for visibility but do not affect
    the user-facing response. Real blocking is reserved for future
    non-streaming surfaces.
    """
    return await _run_pipeline(
        text=text,
        checks=checks,
        span_name="guardrails.output",
        allow_block=False,
        allow_redact=False,
    )


async def _run_pipeline(
    *,
    text: str,
    checks: Sequence[Check],
    span_name: str,
    allow_block: bool,
    allow_redact: bool,
) -> GuardrailResult:
    current_text = text
    results: list[tuple[str, CheckResult]] = []
    redactions = 0

    with _tracer.start_as_current_span(span_name) as parent_span:
        parent_span.set_attribute("guardrails.check_count", len(checks))

        for check in checks:
            with _tracer.start_as_current_span(f"check.{check.name}") as span:
                try:
                    result = await check.run(current_text)
                except Exception as e:
                    # Lenient: a broken check shouldn't break the request.
                    # Record on the span, log, and treat as passed.
                    logger.warning(
                        "Guardrail check %r raised %s — treating as passed",
                        check.name, e,
                    )
                    span.set_attribute("check.errored", True)
                    span.set_attribute("check.error_message", str(e))
                    span.set_attribute("check.passed", True)
                    results.append(
                        (check.name, CheckResult(passed=True, reason="errored"))
                    )
                    continue

                span.set_attribute("check.passed", result.passed)
                if result.reason:
                    span.set_attribute("check.reason", result.reason)
                for k, v in result.metadata.items():
                    span.set_attribute(f"check.{k}", v)

                results.append((check.name, result))

                if result.block:
                    if not allow_block:
                        # Output pipeline: record but do not block.
                        span.set_attribute("check.would_block", True)
                        continue
                    span.set_attribute("check.blocked", True)
                    parent_span.set_attribute("guardrails.blocked_by", check.name)
                    raise GuardrailBlocked(
                        check_name=check.name,
                        reason=result.reason or "blocked",
                    )

                if result.redacted_text is not None and allow_redact:
                    span.set_attribute("check.redacted", True)
                    current_text = result.redacted_text
                    redactions += 1

        parent_span.set_attribute("guardrails.redactions_applied", redactions)
        return GuardrailResult(
            text=current_text,
            redactions_applied=redactions,
            check_results=results,
        )