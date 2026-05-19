"""Base types for guardrail checks.

A `Check` inspects a string (user input or model output) and returns
a `CheckResult` indicating whether the text passed, was redacted, or
should block the request entirely.

The pipeline (`pipeline.py`) runs a list of checks and aggregates
their results into a single `GuardrailResult`. If any check blocks,
the pipeline raises `GuardrailBlocked` — caller code decides what
to do (typically: return a refusal response to the user).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class CheckResult:
    """Outcome of a single check on a piece of text.

    Attributes:
        passed: True if the text is acceptable as-is.
        block: True if this check requires aborting the request.
               Only one of `block` or `redacted_text` should be set.
        redacted_text: If non-None, the check rewrote the input.
                       Subsequent checks operate on the redacted version.
        reason: Human-readable explanation, for span attributes and
                refusal messages.
        metadata: Free-form extra context (e.g. matched patterns).
    """
    passed: bool
    block: bool = False
    redacted_text: str | None = None
    reason: str | None = None
    metadata: dict[str, str | int | float | bool] = field(default_factory=dict)


class Check(Protocol):
    """Contract every guardrail check implements.

    Checks are plain classes (not pydantic models) — `name` is a class
    attribute, `run` is the only required method. Async because future
    checks may call external services (classifiers, moderation APIs).
    """

    name: str

    async def run(self, text: str) -> CheckResult: ...


@dataclass
class GuardrailResult:
    """Aggregated outcome of running a pipeline of checks on one text.

    Returned from `run_input_pipeline` / `run_output_pipeline` when no
    check blocked. Carries the (possibly redacted) text and per-check
    details for telemetry.
    """
    text: str                                # may be redacted, may equal original
    redactions_applied: int = 0
    check_results: list[tuple[str, CheckResult]] = field(default_factory=list)


class GuardrailBlocked(Exception):
    """Raised when a check decides to abort the request.

    The pipeline raises this immediately on the first blocking check;
    subsequent checks do not run. Caller code (typically `agui_glue.py`)
    catches it and converts to a user-facing refusal.
    """

    def __init__(self, check_name: str, reason: str):
        self.check_name = check_name
        self.reason = reason
        super().__init__(f"Blocked by {check_name}: {reason}")