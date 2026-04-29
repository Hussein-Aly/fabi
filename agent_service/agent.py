from __future__ import annotations
import os
from pydantic_ai import Agent, RunContext, ToolReturn
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.ag_ui import StateDeps
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
            StateSnapshotEvent(type=EventType.STATE_SNAPSHOT, snapshot=new_state.model_dump())
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
