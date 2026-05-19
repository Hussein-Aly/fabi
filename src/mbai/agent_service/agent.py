"""Pydantic AI Agent construction.

Owns the single place where the `Agent(...)` object is built:
model selection, system prompt, output_type, deps_type, toolsets,
instrumentation flag.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI
from pydantic_ai import Agent, DeferredToolRequests
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.ui import StateDeps

from mbai.aiserver.config import build_mb_connection_values
from mbai.base.oauth.oauth_helper import OAuthHelper
from pydantic import BaseModel

if TYPE_CHECKING:
    from mbai.base.model import MBConnectionValues

# Path to resources (system prompt text file, etc.)
# Kept here because agent.py is the canonical owner of the system prompt.
_AISERVER_DIR = Path(__file__).parent.parent / "aiserver"
_RESOURCES_DIR = _AISERVER_DIR / "resources"


class AgentState(BaseModel):
    """Per-request agent state, passed via `StateDeps`.

    Used by AG-UI to surface runtime status to the frontend.
    """

    status: str = ""
    connected_tools: list[str] = []
    current_step: str = ""


class LoggingTransport(httpx.AsyncBaseTransport):
    """Pass-through HTTP transport. Currently a no-op placeholder.

    Kept in case we need to inspect raw LLM traffic later. Token counting
    and cost tracking go through Pydantic AI's `RunUsage`, not here.
    """

    def __init__(self) -> None:
        self._transport = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        return await self._transport.handle_async_request(request)


def _get_system_prompt_date() -> str:
    """Generate dynamic date/time string for the system prompt."""
    now = datetime.now()
    return f"The current date and time is {now.strftime('%A, %B %d, %Y at %I:%M:%S %p')}."


def _build_system_prompt() -> str:
    """Compose the system prompt from static text + dynamic date."""
    static_text = (_RESOURCES_DIR / "example_system_prompt.txt").read_text()
    return (
        "Your name is Fabi, the Assistant of the Fabasoft Company"
        f"\n\n ## Infos \n\n {_get_system_prompt_date()} \n {static_text}"
    )


def get_llm_model() -> tuple[OpenAIChatModel, str, str, "MBConnectionValues"]:
    """Build the LLM client for Pydantic AI.

    TODO: replace static OAuth token fetch with an auto-refreshing client.
          Currently re-fetches on every call (per-request agent construction).
          A future singleton-agent migration depends on fixing this first.
    """
    mb_conn_values = build_mb_connection_values()
    llm_url = mb_conn_values.get_frontend_llm_url_for_openai()
    model_name = "mistral-llm" #"gemma-4-moe-llm" 

    token = OAuthHelper.get_oauth_token_via_keycloak_values(mb_conn_values.inspire_keycloak)

    transport = LoggingTransport()
    http_client = httpx.AsyncClient(transport=transport)

    client = AsyncOpenAI(
        base_url=llm_url,
        api_key="unused",  # required by openai SDK but can be a placeholder
        default_headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "X-Username": mb_conn_values.x_username,
        },
        http_client=http_client,
    )

    model = OpenAIChatModel(
        model_name,
        provider=OpenAIProvider(openai_client=client),
    )
    return model, llm_url, model_name, mb_conn_values


def build_agent(
    *,
    model: OpenAIChatModel,
    mcp_toolset,
) -> Agent:
    """Construct the Fabi agent.

    Per-request construction matches current behavior. See module docstring
    for the future singleton direction.

    Args:
        model: configured LLM model (from `get_llm_model()`)
        mcp_toolset: MCP server toolset, possibly wrapped with approval
                     requirements by the caller
    """
    return Agent(
        model=model,
        deps_type=StateDeps[AgentState],
        toolsets=[mcp_toolset],
        output_type=[str, DeferredToolRequests],
        system_prompt=_build_system_prompt(),
    )


def build_refusal_agent(refusal_text: str) -> Agent:
    """Synthetic agent whose only behavior is to emit a fixed refusal.

    Used by the HTTP layer when an input guardrail blocks a request:
    instead of manually constructing an AG-UI event stream, build this
    agent and route it through `AGUIAdapter.dispatch_request` like any
    other run. Guarantees the refusal lands in conversation history.

    Provides both a non-streaming and streaming function because
    AG-UI dispatches in streaming mode.
    """
    from pydantic_ai.models.function import FunctionModel
    from pydantic_ai.messages import ModelResponse, TextPart

    async def refusal_fn(messages, info):
        return ModelResponse(parts=[TextPart(refusal_text)])

    async def refusal_stream_fn(messages, info):
        # Yield the whole refusal as one chunk. The streaming protocol
        # supports multi-chunk responses but there's no benefit here —
        # the text is fixed.
        yield refusal_text

    return Agent(
        FunctionModel(
            function=refusal_fn,
            stream_function=refusal_stream_fn,
        )
    )
