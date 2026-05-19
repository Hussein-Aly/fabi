"""AI gateway: operational concerns around the agent.

Two sub-modules:
- guardrails: input/output checks (PII, injection, refusal detection)
- Usage:   cost computation and token telemetry from RunUsage

Used by `agent_service` and `aiserver`. Both call into the gateway;
the gateway does not call back into them.

Note: telemetry (OpenTelemetry SDK setup) is a sibling package at
`src/mbai/telemetry/`, not nested here — it's app-wide infrastructure
that the gateway uses like everything else.
"""