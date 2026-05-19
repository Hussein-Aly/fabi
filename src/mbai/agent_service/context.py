"""Request context passed into the agent runner.

Carries everything one agent turn needs to know about the request it
belongs to: who is asking, which session, correlation id for tracing.

Currently minimal — auth identity wiring lands in Phase 5/6 when we
introduce telemetry and need to tag spans with user_id.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequestContext:
    """One request's identity and tracing metadata.

    Frozen so it can be safely passed across the runner / gateway boundary
    without anyone mutating it mid-run.
    """

    user_id: str | None = None
    session_id: str | None = None
    correlation_id: str | None = None