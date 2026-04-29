# DMS Agent HITL — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a self-hosted PydanticAI agent service with AG-UI streaming, mock MCP CRUD, and HITL confirmation via a single `confirm_action` frontend tool.

**Architecture:** AGUIAdapter streams SSE to the DMS frontend over a single POST endpoint. Every write action requires the agent to call `confirm_action` (a frontend tool) before executing the backend tool. State lives on the frontend as `DMSState`, travels with every request, and updates flow back via `StateSnapshotEvent`.

**Tech Stack:** Python 3.12, PydanticAI (ag-ui + openai extras), FastAPI, uvicorn, OpenTelemetry, openinference-instrumentation-pydantic-ai, python-dotenv

---

## File Map

```
fabi/
├── agent_service/
│   ├── __init__.py
│   ├── state.py         # Document, SearchResult, DeletionResult, DMSState
│   ├── mock_mcp.py      # MockMCPClient — in-memory CRUD, same interface as real MCP
│   ├── agent.py         # Agent definition, all tool registrations, model factory
│   ├── observability.py # OTel + Langfuse bootstrap, called once at startup
│   └── main.py          # FastAPI app, AGUIAdapter, event stream loop
├── pyproject.toml
└── .env.example
```

---

## Task 1: Project scaffold

**Files:**
- Create: `fabi/pyproject.toml`
- Create: `fabi/.env.example`
- Create: `fabi/agent_service/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "dms-agent"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "pydantic-ai-slim[ag-ui,openai]>=0.0.49",
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "opentelemetry-sdk>=1.25",
    "opentelemetry-exporter-otlp-proto-http>=1.25",
    "openinference-instrumentation-pydantic-ai>=0.1",
    "python-dotenv>=1.0",
]
```

- [ ] **Step 2: Create .env.example**

```bash
# Model — OpenRouter (dev) / vLLM prod (both OpenAI-compatible)
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_API_KEY=your-openrouter-api-key
LLM_MODEL=google/gemma-4-26b-a4b-it:free

# Observability — skip if Langfuse not running locally
LANGFUSE_OTLP_ENDPOINT=http://localhost:3000/api/public/otel
```

- [ ] **Step 3: Create package init and install**

```bash
touch fabi/agent_service/__init__.py
cd fabi && pip install -e .
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .env.example agent_service/__init__.py
git commit -m "chore: scaffold dms-agent project"
```

---

## Task 2: State types

**Files:**
- Create: `fabi/agent_service/state.py`

- [ ] **Step 1: Implement state.py**

```python
from __future__ import annotations
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
    pending_confirmation: dict | None = None
    # pending_confirmation is frontend-only:
    # set when confirm_action ToolCallEvent is received,
    # cleared after the tool result is sent back.
```

- [ ] **Step 2: Commit**

```bash
git add agent_service/state.py
git commit -m "feat: add DMSState and document types"
```

---

## Task 3: Mock MCP client

**Files:**
- Create: `fabi/agent_service/mock_mcp.py`

- [ ] **Step 1: Implement mock_mcp.py**

```python
from __future__ import annotations
from uuid import uuid4
from agent_service.state import Document, DeletionResult, SearchResult


class MockMCPClient:
    def __init__(self) -> None:
        self._store: dict[str, Document] = {}

    def create(self, title: str, content: str) -> Document:
        doc = Document(id=str(uuid4()), title=title, content=content)
        self._store[doc.id] = doc
        return doc

    def read(self, doc_id: str) -> Document:
        return self._store[doc_id]

    def update(self, doc_id: str, changes: dict) -> Document:
        doc = self._store[doc_id].model_copy(update=changes)
        self._store[doc_id] = doc
        return doc

    def delete(self, doc_id: str) -> DeletionResult:
        del self._store[doc_id]
        return DeletionResult(deleted_id=doc_id, success=True)

    def search(self, query: str) -> list[SearchResult]:
        return [
            SearchResult(id=k, title=v.title, score=1.0)
            for k, v in self._store.items()
            if query.lower() in v.title.lower()
        ]
```

- [ ] **Step 2: Commit**

```bash
git add agent_service/mock_mcp.py
git commit -m "feat: add MockMCPClient with in-memory CRUD and search"
```

---

## Task 4: Agent + backend tools

**Files:**
- Create: `fabi/agent_service/agent.py`

- [ ] **Step 1: Implement agent.py**

```python
from __future__ import annotations
import os
from pydantic_ai import Agent, RunContext, ToolReturn
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.ui import StateDeps
from ag_ui.core import StateSnapshotEvent, EventType

from agent_service.mock_mcp import MockMCPClient
from agent_service.state import DMSState, Document, SearchResult, DeletionResult

_mcp: MockMCPClient = MockMCPClient()


def build_model() -> OpenAIModel:
    return OpenAIModel(
        os.getenv("LLM_MODEL", "google/gemma-4-26b-a4b-it:free"),
        provider=OpenAIProvider(
            base_url=os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("LLM_API_KEY"),
        ),
    )


agent: Agent[StateDeps[DMSState], str] = Agent(
    build_model(),
    deps_type=StateDeps[DMSState],
    instructions=(
        "You are a DMS assistant. "
        "For any write action (create, update, delete): call confirm_action first. "
        "Only execute the write tool if confirm_action returns approved=true. "
        "If denied, ask the user whether to try a different approach or stop."
    ),
)


@agent.tool_plain
def search_documents(query: str) -> list[SearchResult]:
    return _mcp.search(query)


@agent.tool
def read_document(
    ctx: RunContext[StateDeps[DMSState]], doc_id: str
) -> ToolReturn:
    doc = _mcp.read(doc_id)
    new_state = ctx.deps.state.model_copy(update={"open_document": doc})
    return ToolReturn(
        return_value=doc,
        metadata=[
            StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=new_state)
        ],
    )


@agent.tool_plain
def create_document(title: str, content: str) -> Document:
    return _mcp.create(title, content)


@agent.tool_plain
def update_document(doc_id: str, changes: dict) -> Document:
    return _mcp.update(doc_id, changes)


@agent.tool_plain
def delete_document(doc_id: str) -> DeletionResult:
    return _mcp.delete(doc_id)
```

- [ ] **Step 2: Commit**

```bash
git add agent_service/agent.py
git commit -m "feat: add agent with CRUD tools and state snapshot on read"
```

---

## Task 5: Observability

**Files:**
- Create: `fabi/agent_service/observability.py`

- [ ] **Step 1: Implement observability.py**

```python
from __future__ import annotations
import logging
import os

logger = logging.getLogger(__name__)


def setup_observability() -> None:
    endpoint = os.getenv("LANGFUSE_OTLP_ENDPOINT")
    if not endpoint:
        logger.info("LANGFUSE_OTLP_ENDPOINT not set — OTel tracing disabled")
        return

    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from openinference.instrumentation.pydantic_ai import PydanticAIInstrumentor

    provider = TracerProvider()
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint))
    )
    PydanticAIInstrumentor().instrument(tracer_provider=provider)
    logger.info("OTel tracing enabled → %s", endpoint)
```

- [ ] **Step 2: Commit**

```bash
git add agent_service/observability.py
git commit -m "feat: add optional Langfuse OTel observability bootstrap"
```

---

## Task 6: AGUIAdapter server endpoint

**Files:**
- Create: `fabi/agent_service/main.py`

- [ ] **Step 1: Implement main.py**

```python
from __future__ import annotations
import json
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse
from pydantic_ai.ui.ag_ui import AGUIAdapter
from pydantic_ai.ui import StateDeps
from ag_ui.core import EventType

from agent_service.agent import agent
from agent_service.observability import setup_observability
from agent_service.state import DMSState

load_dotenv()

logger = logging.getLogger("dms.agent")


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_observability()
    yield


app = FastAPI(lifespan=lifespan)
_adapter = AGUIAdapter(agent, deps=StateDeps(DMSState()))


@app.post("/agent")
async def agent_endpoint(request: Request) -> StreamingResponse:
    async def event_stream():
        async for event in _adapter.run_stream(request):
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

- [ ] **Step 2: Commit**

```bash
git add agent_service/main.py
git commit -m "feat: add AGUIAdapter FastAPI endpoint with event stream logging"
```

---

## Task 7: Smoke test with OpenRouter

Verifies the running service end-to-end with `google/gemma-4-26b-a4b-it:free` via OpenRouter.

- [ ] **Step 1: Set up .env**

```bash
cd fabi
cp .env.example .env
# Edit .env — set LLM_API_KEY to your OpenRouter key
```

- [ ] **Step 2: Start the agent service**

```bash
uvicorn agent_service.main:app --host 0.0.0.0 --port 8001 --reload
```

Expected: `Application startup complete.`

- [ ] **Step 3: Smoke — read request (no confirmation needed)**

```bash
curl -X POST http://localhost:8001/agent \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "thread_id": "smoke-1",
    "run_id": "run-1",
    "messages": [{"role": "user", "content": "Search for any documents", "id": "m1"}],
    "state": {},
    "tools": []
  }'
```

Expected: SSE stream with text response. No errors in server logs.

- [ ] **Step 4: Smoke — write request (confirm_action should fire)**

```bash
curl -X POST http://localhost:8001/agent \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "thread_id": "smoke-2",
    "run_id": "run-2",
    "messages": [{"role": "user", "content": "Create a document called Test Doc with content hello world", "id": "m1"}],
    "state": {},
    "tools": [
      {
        "name": "confirm_action",
        "description": "Ask user to confirm a write action before execution.",
        "parameters": {
          "type": "object",
          "properties": {
            "tool_to_run": {"type": "string"},
            "args": {"type": "object"},
            "description": {"type": "string"}
          },
          "required": ["tool_to_run", "args", "description"]
        }
      }
    ]
  }'
```

Expected: SSE stream includes `tool_call` event with `tool_name: confirm_action`. Agent does NOT call `create_document` in this response — it waits for user approval.

- [ ] **Step 5: Smoke — send approval, verify document created**

Take the `tool_call_id` from the previous response and send the approval:

```bash
curl -X POST http://localhost:8001/agent \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{
    "thread_id": "smoke-2",
    "run_id": "run-3",
    "messages": [
      {"role": "user", "content": "Create a document called Test Doc with content hello world", "id": "m1"},
      {"role": "assistant", "content": "", "id": "m2", "tool_calls": [
        {"id": "<tool_call_id_from_step4>", "type": "function", "function": {"name": "confirm_action", "arguments": "{\"tool_to_run\": \"create_document\", \"args\": {\"title\": \"Test Doc\", \"content\": \"hello world\"}, \"description\": \"Create document Test Doc\"}"}}
      ]},
      {"role": "tool", "content": "{\"approved\": true}", "tool_call_id": "<tool_call_id_from_step4>", "id": "m3"}
    ],
    "state": {},
    "tools": [
      {
        "name": "confirm_action",
        "description": "Ask user to confirm a write action before execution.",
        "parameters": {
          "type": "object",
          "properties": {
            "tool_to_run": {"type": "string"},
            "args": {"type": "object"},
            "description": {"type": "string"}
          },
          "required": ["tool_to_run", "args", "description"]
        }
      }
    ]
  }'
```

Expected: SSE stream includes `tool_call` for `create_document`, then a text response confirming creation. Server logs show both `tool_call` entries.
