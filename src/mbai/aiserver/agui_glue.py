"""AG-UI specific HTTP request handling.

Knows AG-UI's wire format and protocol. Delegates all cross-cutting
concerns (guardrails, usage telemetry) to the `AIGateway`, which is
injected from the route handler.
"""

from __future__ import annotations

import logging
from typing import AsyncIterator

from ag_ui.core import (
    BaseEvent,
    CustomEvent,
    EventType,
    RunAgentInput,
    SystemMessage,
)
from ag_ui.encoder import EventEncoder
from fastapi import Request
from pydantic_ai import AgentRunResult
from pydantic_ai.ui.ag_ui import AGUIAdapter
from starlette.responses import Response, StreamingResponse

from mbai.agent_service.agent import build_refusal_agent
from mbai.agent_service.context import RequestContext
from mbai.agent_service.runner import prepare_agent_run
from mbai.ai_gateway.service import AIGateway

logger = logging.getLogger(__name__)


async def handle_agui_request(
    request: Request,
    body: RunAgentInput,
    gateway: AIGateway,
) -> Response:
    """Handle one AG-UI `POST /agui_agent` request end-to-end.

    1. Gateway pre-run (input checks, redactions).
    2. If blocked → dispatch a synthetic refusal agent.
    3. Otherwise → build and dispatch the real agent.
    4. After agent finishes, `on_complete` calls `gateway.post_run` for
       usage telemetry and output checks, then syncs history.
    """
    ctx = _extract_context(request)
    request_body = await request.json()

    outcome = await gateway.pre_run(request_body)
    if outcome.blocked:
        refusal_agent = build_refusal_agent(outcome.refusal_text)
        return await AGUIAdapter.dispatch_request(
            request,
            agent=refusal_agent,
            on_complete=_make_on_complete(gateway, "refusal-agent"),
            manage_system_prompt="server",
        )

    prepared = await prepare_agent_run(ctx, request_body)

    original_response = await AGUIAdapter.dispatch_request(
        request,
        agent=prepared.agent,
        on_complete=_make_on_complete(gateway, prepared.model_name),
        deferred_tool_results=prepared.deferred_results,
        manage_system_prompt=prepared.manage_system_prompt,
    )

    info_value = (
        f"mcp: {prepared.mcp_url}, llm: {prepared.model_name} \n "
        f"inspire (search and llm): {prepared.inspire_frontend_host}"
    )

    return StreamingResponse(
        _wrap_with_custom_events(original_response.body_iterator, info_value),
        media_type="text/event-stream",
        headers=dict(original_response.headers),
    )


def _extract_context(request: Request) -> RequestContext:
    """Stub. Will pull user_id from JWT claims and session_id from the
    AG-UI thread id."""
    return RequestContext()


def _make_on_complete(gateway: AIGateway, model_name: str):
    """Build an `on_complete` async generator bound to a specific
    gateway and model name.

    The closure captures both so AG-UI sees a clean one-argument
    callback (`async def (result) -> AsyncIterator[BaseEvent]`) while
    we get both pieces of context inside without passing them on the
    wire.
    """
    async def _on_complete(
        result: AgentRunResult,
    ) -> AsyncIterator[BaseEvent]:
        # Gateway post-run: usage telemetry + output guardrails.
        await gateway.post_run(result, model_name)

        # AG-UI-specific: history sync.
        agui_message_list = [
            msg
            for msg in AGUIAdapter.dump_messages(result.all_messages())
            if not isinstance(msg, SystemMessage)
        ]
        yield CustomEvent(
            type=EventType.CUSTOM,
            name="all_messages",
            value=agui_message_list,
        )

    return _on_complete


async def _wrap_with_custom_events(
    body_iterator: AsyncIterator[bytes],
    info_value: str,
) -> AsyncIterator[bytes]:
    """Pass-through wrapper that injects a custom 'info' event after
    AG-UI emits its `RUN_STARTED` event."""
    encoder = EventEncoder()
    async for chunk in body_iterator:
        yield chunk
        if '"type":"RUN_STARTED"' in str(chunk):
            yield encoder.encode(
                CustomEvent(
                    type=EventType.CUSTOM,
                    name="info",
                    value=info_value,
                )
            )