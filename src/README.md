# Fabi AI Server

FastAPI + Pydantic AI chatbot for Fabasoft R&D. Streams via AG-UI to a browser
frontend, talks to a self-hosted Mistral over an OpenAI-compatible endpoint,
and uses MCP for tool access. Single stateless pod, JWT-gated, no DB.

## Architecture at a glance

```
aiserver/  →  agent_service/  →  ai_gateway/
                                  telemetry/
```

`aiserver/` is the HTTP/AG-UI surface. `agent_service/` builds and runs the
agent (protocol-agnostic). `ai_gateway/` adds guardrails and usage telemetry
on top. `telemetry/` provides shared OTel infrastructure. Dependencies only
flow downward — `agent_service/` never imports from `aiserver/`, and so on.

---

## Modules

### `aiserver/` — HTTP surface

How Fabi is exposed to the world. Contains FastAPI routes, AG-UI glue, JWT
auth, and config. Everything protocol-specific lives here.

- **`api_server.py`** — FastAPI app construction, route definitions, lifespan.
  Applies FastAPI auto-instrumentation at app build time (lifespan timing is
  too late). Routes delegate to handlers in `agui_glue.py`.
- **`agui_glue.py`** — AG-UI specific request handling. `handle_agui_request`
  is the entry point for `POST /agui_agent`; `on_complete` is the callback
  fired after the agent finishes, where usage telemetry, output guardrails,
  and history sync are wired in. Refusal-agent dispatch lives here too.
- **`config.py`** — Pydantic-settings model for all environment-driven config
  (Keycloak, Inspire, telemetry mode, etc.).
- **`api_server_auth.py`** — JWT validation dependency.
- **`api_model.py`** — Request/response models.
- **`exceptions.py`** — App-wide exception types.
- **`mcp_helpers.py`** — MCP toolset construction.
- **`dummy_jwt.py`** — Dev-only JWT generation for testing.

### `agent_service/` — what the AI does

Protocol-agnostic agent logic. Knows about Pydantic AI, the model, the system
prompt, and tools — but nothing about HTTP, AG-UI, or guardrails.

- **`agent.py`** — `build_agent` (the real agent) and `build_refusal_agent`
  (synthetic agent using `FunctionModel` for guardrail-blocked requests so
  refusals flow through the same dispatch path and sync to history). Holds
  the model construction (`get_llm_model`) and system prompt assembly.
- **`runner.py`** — `prepare_agent_run` is the orchestrator called per
  request: builds the model and MCP toolset, constructs the agent, runs the
  input guardrails pipeline, returns a `PreparedRun` dataclass. Raises
  `GuardrailBlocked` if any input check blocks.
- **`context.py`** — `RequestContext` stub. Will carry `user_id` /
  `session_id` from JWT claims once that's wired up.
- **`tools.py`** — Pydantic AI tool registrations beyond MCP (e.g. helpers
  like `read_file`, `do_vector_search`).

### `ai_gateway/` — operational concerns

Gateway-style cross-cutting features applied to every agent run. Each
sub-feature has its own `pipeline.py` entry point; the HTTP layer never
reaches into internals.

#### `ai_gateway/guardrails/`

Input and output policy enforcement.

- **`base.py`** — The `Check` protocol, `CheckResult`, `GuardrailResult`, and
  the `GuardrailBlocked` exception every check can raise.
- **`pipeline.py`** — `run_input_pipeline` (allows blocking and text
  redaction) and `run_output_pipeline` (detection-only, since AG-UI has
  already streamed by then).
- **`input/`** — Active input checks:
  - **`length_cap.py`** — Hard length limit (default 20,000 chars). Blocks.
  - **`pii_redactor.py`** — Regex redaction of emails, phone numbers, IBANs,
    credit cards, IPv4. Redacts (doesn't block) so the agent sees
    `[REDACTED_*]` placeholders.
  - **`injection.py`** — Pattern-based prompt-injection detector. Blocks on
    known shapes (instruction overrides, ChatML/Llama role markers, etc.).
    Deliberately low-effort defense — catches accidental and lazy attacks.
- **`output/`** — Scaffolding only. Pipeline is wired in `on_complete`;
  `default_output_checks()` returns `[]` until real checks are added.

#### `ai_gateway/usage/`

Observational cost and token telemetry. No enforcement.

- **`cost.py`** — `compute_cost_eur` (token math) and `emit_cost_telemetry`
  (opens a dedicated `usage.cost` span with `cost.eur`, `tokens.*`,
  `model.name`; increments the `llm.cost.eur` counter metric). Per-1k EUR
  rates are module-level constants.
- **`pipeline.py`** — `run_usage_pipeline` is the entry point called from
  `on_complete`. Mirrors the guardrails pipeline shape; swallows telemetry
  errors so they never break a user response.

### `telemetry/` — OTel infrastructure

Shared observability plumbing. Used by everything else but doesn't import
from anywhere else in the app.

- **`setup.py`** — `configure_telemetry` (called from lifespan) sets up
  TracerProvider, MeterProvider, HTTPX instrumentation, and Pydantic AI's
  `Agent.instrument_all()`. `instrument_fastapi(app)` is called separately
  from `api_server.py` at app construction (timing reasons). Three exporter
  modes via settings: `jsonl` (default), `console`, `langfuse`.
- **`exporters.py`** — `JsonlFileSpanExporter` and `JsonlFileMetricExporter`
  for the default file-based mode. `FilteringSpanExporter` wraps any inner
  exporter and drops spans matching configured regex patterns (used to
  suppress per-chunk ASGI `http send` / `http receive` noise from streaming
  responses).
- **`logging_filter.py`** — `TraceContextFilter` injects the current
  trace_id and span_id into every log record, enabling log↔trace
  correlation without a co-located backend.
- **`logging_config.py`** — `configure_logging` sets up the JSON log
  formatter and attaches the trace context filter. Called at app startup.

---

## How a request flows

1. `POST /agui_agent` arrives. FastAPI middleware opens `POST /agui_agent`
   server span.
2. `handle_agui_request` (in `agui_glue.py`) calls
   `prepare_agent_run` (in `agent_service/runner.py`).
3. `prepare_agent_run` builds the agent and runs the input guardrails
   pipeline. PII is redacted in place; injection raises `GuardrailBlocked`.
4. If blocked → build a refusal agent and dispatch it via AG-UI like a
   normal run, so history syncs identically.
5. Otherwise → dispatch the real agent via `AGUIAdapter.dispatch_request`.
   Pydantic AI emits `agent run`, `chat mistral-llm`, `running tool` spans.
6. When the agent finishes, `on_complete` fires:
   - `run_usage_pipeline` emits the `usage.cost` span + counter
   - `run_output_pipeline` runs output guardrails (detection only)
   - A `CustomEvent("all_messages")` is yielded so the frontend can sync
     history
7. AG-UI emits `RUN_FINISHED`. Response stream closes.

---

## Running it

```bash
python src/mbai/aiserver/api_server.py
```

Frontend at `http://localhost:9001/agui`. Health check at `/health-check`.

Default telemetry mode writes to `traces/traces.jsonl` and
`traces/metrics.jsonl`. Switch via `OTEL_EXPORTER=langfuse` (also needs
Langfuse credentials).

## Known limits and follow-ups

- `_extract_context` is a stub — user/session IDs are not yet pulled from
  JWT claims.
- `_PRICING` rates in `cost.py` are placeholders; replace with company
  chargeback rates when defined.
- Output guardrails on AG-UI are detection-only by design (streaming can't
  be unsent). For future non-streaming surfaces, the refusal-agent pattern
  can be reused as a substitution agent.
- `mindbreeze-protobuf` pins protobuf 4 while Langfuse v3 + OTel OTLP need
  protobuf 5. Dockerfile force-installs telemetry deps via `--no-deps`;
  runtime warnings appear but functionality works.