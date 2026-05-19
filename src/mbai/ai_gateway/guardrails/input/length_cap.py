"""Trivial sanity check: reject messages longer than a cap.

Catches obvious abuse (someone pasting a 10MB log) and accidental
runaway client behavior. Not a security control — a sanity control.
"""

from __future__ import annotations

from mbai.ai_gateway.guardrails.base import Check, CheckResult


class LengthCap(Check):
    name = "length_cap"

    def __init__(self, max_chars: int = 20_000) -> None:
        self._max_chars = max_chars

    async def run(self, text: str) -> CheckResult:
        n = len(text)
        if n > self._max_chars:
            return CheckResult(
                passed=False,
                block=True,
                reason=f"input exceeds {self._max_chars} characters (got {n})",
                metadata={"length": n, "limit": self._max_chars},
            )
        return CheckResult(passed=True, metadata={"length": n})