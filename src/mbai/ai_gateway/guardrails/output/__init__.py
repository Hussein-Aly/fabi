"""Output guardrail checks (PII leakage, refusal detection, etc.).

Output pipeline is detection-only on streaming AG-UI: checks record
findings on spans but do not block or modify the response (it has
already been streamed to the user).
"""

from __future__ import annotations


def default_output_checks():
    """Return the standard output check list. Empty for now — fills in
    when string-level output filtering is implemented.
    """
    return []