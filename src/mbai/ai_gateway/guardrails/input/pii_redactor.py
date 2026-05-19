"""Regex-based PII redactor.

Replaces common PII patterns in user input with `[REDACTED_<TYPE>]`
markers so the agent sees structure but not the sensitive content.
This is intentionally a simple, predictable baseline — catches obvious
shapes (emails, phone numbers, IBANs, credit cards). For higher recall
on harder cases (names, addresses, contextual PII), swap in a real NER
solution like Presidio later.

Behaviour: REDACTS (does not block). Redaction produces a modified
string the pipeline passes to subsequent checks and to the agent.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from mbai.ai_gateway.guardrails.base import Check, CheckResult


@dataclass(frozen=True)
class _Pattern:
    """One PII pattern: a label, a regex, and a replacement marker."""
    name: str
    regex: re.Pattern[str]
    replacement: str


# Patterns are deliberately conservative — better to under-redact than
# corrupt legitimate text. Order matters slightly (longer/more specific
# patterns first to avoid being shadowed by shorter ones).
_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern(
        name="credit_card",
        # 13–19 digits with optional spaces or dashes between groups.
        # Not Luhn-checked — catches the shape, accepts some false positives.
        regex=re.compile(r"\b(?:\d[ -]?){12,18}\d\b"),
        replacement="[REDACTED_CREDIT_CARD]",
    ),
    _Pattern(
        name="iban",
        # IBAN: 2 letters + 2 digits + up to 30 alphanumerics.
        regex=re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
        replacement="[REDACTED_IBAN]",
    ),
    _Pattern(
        name="email",
        regex=re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
        replacement="[REDACTED_EMAIL]",
    ),
    _Pattern(
        name="phone",
        # International-ish: optional +, country/area, separators.
        # Requires 8+ digits total to avoid matching short numbers.
        regex=re.compile(r"\+?\d[\d\s().-]{7,}\d"),
        replacement="[REDACTED_PHONE]",
    ),
    _Pattern(
        name="ipv4",
        regex=re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
        replacement="[REDACTED_IP]",
    ),
)


class PIIRedactor(Check):
    name = "pii_redactor"

    async def run(self, text: str) -> CheckResult:
        redacted = text
        redactions_by_type: dict[str, int] = {}

        for pattern in _PATTERNS:
            new_text, count = pattern.regex.subn(pattern.replacement, redacted)
            if count > 0:
                redactions_by_type[pattern.name] = count
                redacted = new_text

        if not redactions_by_type:
            return CheckResult(passed=True)

        total = sum(redactions_by_type.values())
        # Metadata gets serialized as span attributes — keep keys simple.
        metadata: dict[str, str | int | float | bool] = {
            "redaction_count": total,
        }
        for ptype, count in redactions_by_type.items():
            metadata[f"redacted_{ptype}"] = count

        return CheckResult(
            passed=True,                # redaction is not a failure
            redacted_text=redacted,
            reason=f"redacted {total} PII pattern(s): {','.join(redactions_by_type)}",
            metadata=metadata,
        )