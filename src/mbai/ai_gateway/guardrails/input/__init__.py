"""Input guardrail checks (PII, injection, etc.).

The default check list is built by `default_input_checks()`. Order
matters — cheap checks first, then redaction, then pattern matching
on the (possibly redacted) text.
"""

from mbai.ai_gateway.guardrails.input.injection import InjectionHeuristic
from mbai.ai_gateway.guardrails.input.length_cap import LengthCap
from mbai.ai_gateway.guardrails.input.pii_redactor import PIIRedactor

__all__ = [
    "InjectionHeuristic",
    "LengthCap",
    "PIIRedactor",
    "default_input_checks",
]


def default_input_checks():
    """Return the standard input check list, in execution order.

    Order rationale:
    1. LengthCap          — cheap, blocks obvious abuse first
    2. PIIRedactor        — sanitizes text before pattern matching
    3. InjectionHeuristic — runs on cleaned text
    """
    return [
        LengthCap(max_chars=20_000),
        PIIRedactor(),
        InjectionHeuristic(),
    ]