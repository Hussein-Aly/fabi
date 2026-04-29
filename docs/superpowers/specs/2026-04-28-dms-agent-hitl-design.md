# DMS Agent — HITL & Core Architecture Design

**Date:** 2026-04-28  
**Scope:** v1 — HITL flow, state management, tool communication, MCP integration, mock MCP  
**Stack:** PydanticAI · AG-UI (`AGUIApp`) · MCP · Ollama (dev) / vLLM (prod) · OpenTelemetry → Langfuse (self-hosted)

---

## 1. Architecture Overview

An external Python service hosts a PydanticAI agent exposed via `AGUIApp` (ASGI/SSE). The DMS frontend communicates with it using the AG-UI protocol — each turn is a new HTTP request carrying full message history and current state. The agent reads documents and executes write actions against the DMS via an MCP server. All write actions require user confirmation before execution.

```
DMS Frontend
  │  RunAgentInput { messages, state, tools }
  ▼
AGUIAdapter (FastAPI POST /agent)
  │  event_stream loop → Langfuse (every ToolCallEvent / ToolResultEvent)
  │  StateDeps[DMSState]
  ▼
PydanticAI Agent
  ├── Read tools (auto-run)     → MCP server
  ├── Write tools (execute)     → MCP server
  └── confirm_action            → ToolCallEvent → Frontend modal
                                    ← ToolResultEvent (next request)

Future: background durable ops
  TemporalAgent (same agent) → Temporal Worker → Temporal Server
```

---

## 2. State Management

### Design

AG-UI is frontend-authoritative by design. `DMSState` lives on the frontend, travels to the agent with every request, and is updated via `StateSnapshotEvent` SSE events.

```python
from pydantic import BaseModel

class Document(BaseModel):
    id: str
    title: str
    content: str

class SearchResult(BaseModel):
    id: str
    title: str
    score: float

class DeletionResult(BaseModel):
    deleted_id: str
    success: bool

class DMSState(BaseModel):
    open_document: Document | None = None
    search_results: list[SearchResult] = []
    pending_confirmation: dict | None = None  # frontend-only: set when confirm_action ToolCallEvent received, cleared after result sent
```

### Flow

```
Request N:   Frontend sends RunAgentInput.state = { open_document: {...}, ... }
Agent run:   ctx.deps.state is validated DMSState
State change: tool returns StateSnapshotEvent(snapshot=new_state)
Response:    SSE StateSnapshotEvent → frontend updates local state
Request N+1: Frontend sends updated state
```

### Tab-close recovery

Frontend persists `RunAgentInput.messages` + `DMSState` (including `pending_confirmation`) to `localStorage` after every response. On return:
- If `pending_confirmation` is set → re-render modal immediately
- User decides → send new request with tool result appended to messages
- Clear `pending_confirmation` from state after resolution

---

## 3. Tool Structure

### Principle

One frontend tool schema (`confirm_action`) handles all write confirmations. No per-action frontend schemas. No confirm/execute pairs. Backend tools are the single source of truth for write operations.

### Backend tools (Python)

```python
from pydantic_ai import Agent, RunContext, ToolReturn
from pydantic_ai.ui import StateDeps
from ag_ui.core import StateSnapshotEvent, EventType

agent = Agent(
    'openai:gpt-4o',  # swap model string for Ollama/vLLM
    deps_type=StateDeps[DMSState],
    instructions=(
        "You are a DMS assistant. "
        "For any write action (create, update, delete): call confirm_action first. "
        "Only execute the write tool if confirm_action returns approved=true. "
        "If denied, ask the user whether to try a different approach or stop."
    ),
)

# ── Read-only (auto-run, no confirmation) ─────────────────────────────────

@agent.tool_plain
def search_documents(query: str) -> list[SearchResult]:
    return mcp.search(query)

@agent.tool
def read_document(ctx: RunContext[StateDeps[DMSState]], doc_id: str) -> ToolReturn:
    doc = mcp.read(doc_id)
    new_state = ctx.deps.state.model_copy(update={'open_document': doc})
    return ToolReturn(
        return_value=doc,
        metadata=[StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=new_state)],
    )

# ── Write (execute only after confirm_action returns approved=true) ────────

@agent.tool_plain
def delete_document(doc_id: str) -> DeletionResult:
    return mcp.delete(doc_id)

@agent.tool_plain
def create_document(title: str, content: str) -> Document:
    return mcp.create(title, content)

@agent.tool_plain
def update_document(doc_id: str, changes: dict) -> Document:
    return mcp.update(doc_id, changes)
```

### Frontend tool (sent by DMS UI in every RunAgentInput.tools)

```jsonc
{
  "name": "confirm_action",
  "description": "Ask the user to confirm a write action before execution.",
  "parameters": {
    "type": "object",
    "properties": {
      "tool_to_run":  { "type": "string", "description": "Backend tool name to call on approval" },
      "args":         { "type": "object", "description": "Args to pass to tool_to_run" },
      "description":  { "type": "string", "description": "Human-readable summary shown in the modal" }
    },
    "required": ["tool_to_run", "args", "description"]
  }
}
```

The DMS frontend intercepts `ToolCallEvent` for `confirm_action`, renders a modal, and sends the result back as a new request with `{ approved: bool }` appended to message history.

---

## 4. HITL Flow

### Confirm → approve

```
User:    "Delete the Q4 Report"
Agent:   confirm_action(
           tool_to_run="delete_document",
           args={"doc_id": "abc123"},
           description="Permanently delete 'Q4 Report'"
         )
AG-UI:   ToolCallEvent → frontend renders modal
User:    clicks Confirm
Frontend: sends new request, messages include ToolResult { approved: true }
Agent:   calls delete_document(doc_id="abc123")
Agent:   "Q4 Report has been deleted."
```

### Confirm → deny → re-entry

```
User:    clicks Deny
Frontend: sends new request, messages include ToolResult { approved: false }
Agent:   "Understood — deletion cancelled. Should I try something else,
          or would you like to leave it as is?"
User:    "Leave it"
Agent:   "No problem."
```

### Sequential guarantee

Agent only calls one `confirm_action` per turn. Write tools are only called within the same turn after a confirmed result. No batching. No parallel confirmations. This is enforced via system prompt instructions, not a technical constraint — test this behavior early against your chosen model.

---

## 5. MCP Integration

### v1 — Mock MCP

Mock MCP is a local Python class implementing the same interface as the real MCP server. Swap in `MCPServerStreamableHTTP` for production with zero agent changes.

```python
# mock_mcp.py
class MockMCPClient:
    def __init__(self) -> None:
        self._store: dict[str, Document] = {}

    def search(self, query: str) -> list[SearchResult]:
        return [
            SearchResult(id=k, title=v.title, score=1.0)
            for k, v in self._store.items()
            if query.lower() in v.title.lower()
        ]

    def read(self, doc_id: str) -> Document:
        return self._store[doc_id]

    def create(self, title: str, content: str) -> Document:
        doc = Document(id=str(uuid4()), title=title, content=content)
        self._store[doc.id] = doc
        return doc

    def update(self, doc_id: str, changes: dict) -> Document:
        doc = self._store[doc_id].model_copy(update=changes)
        self._store[doc_id] = doc
        return doc

    def delete(self, doc_id: str) -> DeletionResult:
        del self._store[doc_id]
        return DeletionResult(deleted_id=doc_id, success=True)

mcp = MockMCPClient()
```

### Production MCP

```python
from pydantic_ai.mcp import MCPServerStreamableHTTP

mcp_server = MCPServerStreamableHTTP('http://dms-internal/mcp')
agent = Agent('openai:gpt-4o', toolsets=[mcp_server.defer_loading()])
```

`defer_loading()` prevents all 50+ tool schemas from entering the context window — tools load on demand. Use this from day one; it costs nothing in v1.

---

## 6. AGUIAdapter Setup

Use `AGUIAdapter` directly instead of `AGUIApp` to intercept every event in one place before it streams to the frontend. This enables centralised logging to Langfuse without touching each tool function.

```python
# agent_service/main.py
import json
import logging
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse
from pydantic_ai.ui.ag_ui import AGUIAdapter
from pydantic_ai.ui import StateDeps
from ag_ui.core import EventType

from .agent import agent
from .state import DMSState

app = FastAPI()
adapter = AGUIAdapter(agent, deps=StateDeps(DMSState()))
logger = logging.getLogger("dms.agent")


@app.post('/agent')
async def agent_endpoint(request: Request) -> StreamingResponse:
    async def event_stream():
        async for event in adapter.run_stream(request):
            if event.type == EventType.TOOL_CALL:
                logger.info(json.dumps({
                    "event": "tool_call",
                    "tool": event.tool_name,
                    "id": event.tool_call_id,
                }))
            elif event.type == EventType.TOOL_RESULT:
                logger.info(json.dumps({
                    "event": "tool_result",
                    "tool": event.tool_name,
                }))
            yield event

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

Run: `uvicorn agent_service.main:app --host 0.0.0.0 --port 8001`

Auth (Keycloak) sits in front as a reverse-proxy — agent service stays auth-agnostic in v1.

---

## 7. Observability

OpenTelemetry tracing via PydanticAI's built-in OTel support. Langfuse self-hosted — all environments.

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from openinference.instrumentation.pydantic_ai import PydanticAIInstrumentor

provider = TracerProvider()
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://langfuse-host/api/public/otel")  # self-hosted
    )
)
PydanticAIInstrumentor().instrument(tracer_provider=provider)
```

Every agent run, tool call, and MCP request is traced automatically. Langfuse receives spans via OTLP and surfaces them as traces with token usage, latency, and tool call trees.

---

## 8. Roadmap Compatibility

| Concern | v1 | Future |
|---|---|---|
| Tool count | 3 CRUD via mock MCP | `MCPServerStreamableHTTP` + `defer_loading()` |
| Progressive disclosure | `defer_loading()` (on from day 1) | Semantic tool search layer if needed |
| Subagents | Single agent | Agent-as-tool per domain (search, compliance, edit) |
| Context management | Client sends last N turns (start: 20 turns = user+agent+tool pairs) | Server-side turn summarization |
| State persistence | localStorage | Move to DB; `StateDeps` interface unchanged |
| HITL mechanism | `confirm_action` frontend tool | Evaluate `DeferredToolRequests` if moving off AGUIApp |
| Audit/compliance | OTel → Langfuse self-hosted | Structured audit log from tool call events |
| Durable/long-running ops | Not needed | `TemporalAgent` wrapping same agent; separate worker process |
| Temporal HITL | N/A | Temporal workflow signals (separate from chat HITL) |

---

## 9. Open Questions

1. ~~Does `AGUIApp` expose a hook to intercept `ToolCallEvent` before it streams?~~ Resolved: use `AGUIAdapter.run_stream()` event loop instead of `AGUIApp` — intercepts all events in one place before streaming.
2. Keycloak token forwarding to MCP server — skipped for v1 (no auth). Future: verify MCP client supports per-request bearer token injection when wiring vLLM gateway.
