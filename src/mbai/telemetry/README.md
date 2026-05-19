# Telemetry

OpenTelemetry setup for the Fabi AI server. Configures traces, metrics,
and log↔trace correlation once at app startup.

## What this module gives you

- **Traces** — Pydantic AI agent runs, model calls, tool calls, plus
  auto-instrumented FastAPI routes and outbound HTTPX calls.
- **Metrics** — token usage histogram (`gen_ai.client.token.usage`),
  cost histogram (`operation.cost`), HTTP duration/count from FastAPI.
- **Log correlation** — every log record carries the current `trace_id`
  and `span_id` so logs and traces are joinable by ID.

## Modes (selected by `OTEL_EXPORTER` env var)

| Mode      | Traces go to              | Metrics go to            |
|-----------|---------------------------|--------------------------|
| `jsonl`   | `traces/traces.jsonl`     | `traces/metrics.jsonl`   |
| `langfuse`| Langfuse UI               | `traces/metrics.jsonl`   |

Langfuse only accepts traces. Metrics always land in JSONL until the
corporate OTel endpoint exists (planned Q2/Q3).

#### traces exmple

POST /agui_agent (root SERVER span)
├── guardrails.input
│   ├── check.length_cap
│   ├── check.pii_redactor (redacted 2 PII)
│   └── check.injection_heuristic
├── agent run
│   ├── chat mistral-llm
│   ├── POST (outbound to LLM)
│   ├── running tool (list_teamrooms)
│   ├── POST (outbound)
│   └── chat mistral-llm
└── guardrails.output (0 checks)

Logs always go to stdout (handled by `aiserver/logging_config.py`).

## Environment variables

```bash
OTEL_EXPORTER=jsonl                    # or "langfuse"
OTEL_JSONL_PATH=traces/traces.jsonl    # optional, default shown
OTEL_METRICS_JSONL_PATH=traces/metrics.jsonl
OTEL_METRIC_EXPORT_INTERVAL_MS=60000   # metric snapshot interval
```

Local dev: leave `OTEL_EXPORTER` unset (defaults to `jsonl`).
Fabi deployment: set `OTEL_EXPORTER=langfuse`.

## Module layout

- `setup.py`        — `configure_telemetry(app)`, called from FastAPI lifespan.
- `exporters.py`    — `JsonlFileSpanExporter`, `JsonlFileMetricExporter`.
- `logging_filter.py` — `TraceContextFilter` for log↔trace correlation.

The rest of the codebase only calls `trace.get_tracer(__name__)` and
`metrics.get_meter(__name__)` via the OTel SDK directly. Nothing
imports from this module except the FastAPI lifespan hook and
`logging_config.py`.

## Migrating to the corporate OTel endpoint

When the corp endpoint lands, add a third mode (`otlp`) in `setup.py`
that constructs an `OTLPSpanExporter` pointing at the corp URL. No
changes anywhere else.

If `mindbreeze-protobuf` is still pinned to protobuf 4 at that point,
the OTLP exporter package will conflict. Two workarounds:
1. Deploy an OpenTelemetry Collector sidecar that reads
   `traces/traces.jsonl` (filelog receiver) and forwards as OTLP.
2. Wait for mindbreeze to upgrade to protobuf 5.

## Known gotcha

`langfuse` and `opentelemetry-exporter-otlp-proto-http` are installed
outside `pyproject.toml` (force-installed in the Dockerfile) because
they pull `protobuf>=5`, which conflicts with `mindbreeze-protobuf`
pinned to `protobuf==4.25.8`. The packages coexist at runtime; some
protobuf warnings appear in logs. See `Dockerfile` for the install
incantation.

## Verification

```bash
# Send a request to /agui_agent
tail -5 traces/traces.jsonl | jq .name           # spans for the request
tail -5 traces/metrics.jsonl | jq '...'          # metric snapshots every 60s

# Find a log line with a trace_id, grep it in the trace file:
grep <trace_id_from_log> traces/traces.jsonl | jq .name
```