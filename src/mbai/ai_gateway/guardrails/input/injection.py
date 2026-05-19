"""Heuristic prompt-injection detector.

Pattern matches against known prompt-injection shapes:
- "ignore previous instructions" and similar overrides
- Role-marker tokens (Llama, ChatML) injected into user input
- Direct requests to reveal the system prompt

This is intentionally NOT a serious adversarial defense — it catches
low-effort attacks (copy-pasted jailbreak prompts, accidental token
leakage). Real prompt-injection attackers will trivially evade it.
For higher confidence, swap to a dedicated classifier model later.

Behaviour: BLOCKS on any match. Unlike PII redaction, there's no
sensible way to "redact" an injection attempt — the whole intent is
hostile, so the right answer is to refuse.
"""

from __future__ import annotations

import re

from mbai.ai_gateway.guardrails.base import Check, CheckResult


# Each pattern is a (name, regex) tuple. Names appear in spans for
# diagnosis. Patterns are case-insensitive.
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "instruction_override",
        re.compile(
            r"\b(ignore|disregard|forget)\b[^.]{0,40}\b"
            r"(previous|prior|earlier|above|all|the|your)\b[^.]{0,40}\b"
            r"(instructions?|prompts?|rules?|directives?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "reveal_system_prompt",
        re.compile(
            r"\b(show|reveal|tell|print|repeat|output|display)\b[^.]{0,30}\b"
            r"(your|the)\b[^.]{0,30}\b"
            r"(system prompt|initial prompt|instructions|directive)",
            re.IGNORECASE,
        ),
    ),
    (
        "role_marker_chatml",
        # ChatML / OpenAI-style role markers leaking into user input.
        re.compile(r"<\|(im_start|im_end|system|user|assistant)\|>"),
    ),
    (
        "role_marker_llama",
        # Llama-style role markers.
        re.compile(r"\[/?INST\]|<</?SYS>>"),
    ),
)


class InjectionHeuristic(Check):
    name = "injection_heuristic"

    async def run(self, text: str) -> CheckResult:
        for pattern_name, pattern in _PATTERNS:
            match = pattern.search(text)
            if match:
                return CheckResult(
                    passed=False,
                    block=True,
                    reason=f"detected injection pattern: {pattern_name}",
                    metadata={
                        "pattern": pattern_name,
                        "matched_text": match.group(0)[:80],  # truncate for span size
                    },
                )

        return CheckResult(passed=True)