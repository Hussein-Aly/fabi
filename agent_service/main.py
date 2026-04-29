from __future__ import annotations
import json
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from starlette.responses import StreamingResponse
from pydantic_ai.ag_ui import handle_ag_ui_request, StateDeps

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


@app.post("/agent")
async def agent_endpoint(request: Request) -> StreamingResponse:
    """Handle AG-UI agent requests, streaming SSE events.

    Tool call/result events are logged by parsing the SSE JSON payloads.
    The plan referenced AGUIAdapter from pydantic_ai.ui.ag_ui, which does not
    exist in pydantic-ai 1.x; the equivalent public API is handle_ag_ui_request
    from pydantic_ai.ag_ui (returns a StreamingResponse directly).
    """
    deps = StateDeps(DMSState())

    # Wrap the streaming response to intercept and log tool events.
    async def logged_event_stream():
        response = await handle_ag_ui_request(agent, request, deps=deps)
        buffer = ""
        async for chunk in response.body_iterator:
            text = chunk.decode() if isinstance(chunk, (bytes, bytearray)) else chunk
            buffer += text
            *complete_frames, buffer = buffer.split("\n\n")
            for frame in complete_frames:
                for line in frame.splitlines():
                    if line.startswith("data: "):
                        try:
                            payload = json.loads(line[6:])
                            event_type = payload.get("type", "")
                            if event_type == "TOOL_CALL_START":
                                logger.info(json.dumps({
                                    "event": "tool_call",
                                    "tool": payload.get("toolCallName"),
                                    "id": payload.get("toolCallId"),
                                }))
                            elif event_type == "TOOL_CALL_RESULT":
                                logger.info(json.dumps({
                                    "event": "tool_result",
                                    "tool": payload.get("toolCallName"),
                                }))
                        except (json.JSONDecodeError, AttributeError):
                            pass
                yield frame + "\n\n"
        if buffer:
            yield buffer

    return StreamingResponse(logged_event_stream(), media_type="text/event-stream")
