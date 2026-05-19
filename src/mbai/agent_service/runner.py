"""Public entry point for preparing one agent turn.

`prepare_agent_run` builds the LLM model, MCP toolset, the Pydantic AI
agent, and parses request-derived inputs (deferred tool approvals). It
returns a `PreparedRun` that the HTTP layer can hand to AG-UI's
`dispatch_request`.

This module deliberately does NOT call `AGUIAdapter.dispatch_request` —
that's the HTTP layer's job (`aiserver/agui_glue.py`). It also does NOT
run input guardrails — those are owned by the `AIGateway` and run
before this function is called. Keeping the runner free of AG-UI and
guardrail imports leaves the door open to non-streaming and non-AG-UI
surfaces later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic_ai import Agent, DeferredToolResults, ToolApproved, ToolDenied

from mbai.agent_service.agent import build_agent, get_llm_model
from mbai.agent_service.context import RequestContext
from mbai.agent_service.tools import register_tools
from mbai.aiserver.mcp_helpers import get_mcp_via_http_streamable

# Tools that require user approval before execution.
# Lives here (not in `tools.py`) because it's a policy decision, not a
# tool definition. May move into `ai_gateway/` later if approval policy
# becomes a gateway concern.
_TOOLS_REQUIRING_APPROVAL: set[str] = {"send_email", "list_holidays"}

# Debug toggle for the "new version" of deferred tool handling that
# supports overrideArgs.
# TODO: remove the hardcoded destination_filter override below before
#       production; it currently overwrites every user approval.
_ENABLE_NEW_DEFERRED_VERSION = True


@dataclass
class PreparedRun:
    """Everything the HTTP layer needs to dispatch an agent run.

    Returned by `prepare_agent_run`. The HTTP layer passes `agent` and
    `deferred_results` to `AGUIAdapter.dispatch_request`, and uses the
    metadata fields to populate AG-UI custom events.
    """

    agent: Agent
    deferred_results: DeferredToolResults | None
    manage_system_prompt: Literal["server", "client"]

    # Metadata for the custom info event injected after RUN_STARTED.
    model_name: str
    llm_url: str
    mcp_url: str
    inspire_frontend_host: str


async def prepare_agent_run(
    ctx: RequestContext,
    request_body: dict[str, Any],
) -> PreparedRun:
    """Build the agent and parse request-derived inputs for one turn.

    Pure agent assembly — does not run guardrails or any cross-cutting
    policy. The `AIGateway` owns those concerns and runs `pre_run`
    before this function is called.

    Args:
        ctx: request identity (user_id, session_id, correlation_id).
             Currently unused.
        request_body: parsed JSON body from the incoming HTTP request.
                      Used to extract `forwardedProps.toolApprovals`.
    """
    model, llm_url, model_name, mb_conn_values = get_llm_model()
    mcp_server, mcp_url = get_mcp_via_http_streamable()

    approved_mcp = mcp_server.approval_required(
        lambda ctx_, tool_def, tool_args: tool_def.name in _TOOLS_REQUIRING_APPROVAL
    )

    agent = build_agent(
        model=model,
        mcp_toolset=approved_mcp,
    )
    register_tools(agent, mb_conn_values)

    deferred = _parse_deferred_approvals(request_body)

    return PreparedRun(
        agent=agent,
        deferred_results=deferred,
        manage_system_prompt="server",
        model_name=model_name,
        llm_url=llm_url,
        mcp_url=mcp_url,
        inspire_frontend_host=mb_conn_values.inspire_frontend_host,
    )


def _parse_deferred_approvals(
    request_body: dict[str, Any],
) -> DeferredToolResults | None:
    """Convert AG-UI's `forwardedProps.toolApprovals` into a Pydantic AI
    `DeferredToolResults`.

    Two code paths preserved verbatim from pre-refactor:
    - Legacy: approvals as bools/ToolApproved-shaped values, passed through.
    - New: approvals as `{approved, overrideArgs}` dicts, converted to
      `ToolApproved(override_args=...)` or `ToolDenied`.
    """
    approvals = request_body.get("forwardedProps", {}).get("toolApprovals")
    if not approvals:
        return None

    if not _ENABLE_NEW_DEFERRED_VERSION:
        return DeferredToolResults(
            approvals={tc_id: approved for tc_id, approved in approvals.items()}
        )

    processed: dict[str, Any] = {}
    for tc_id, decision in approvals.items():
        # TODO: remove the hardcoded override — currently overwrites every
        #       user approval with destination_filter=Japan. Bug, not feature.
        decision = dict(approved=True, overrideArgs={"destination_filter": "Japan"})

        if isinstance(decision, dict):
            if decision.get("approved"):
                overrides = decision.get("overrideArgs", {})
                processed[tc_id] = ToolApproved(override_args=overrides)
            else:
                processed[tc_id] = ToolDenied("User denied")
        else:
            processed[tc_id] = decision

    return DeferredToolResults(approvals=processed)