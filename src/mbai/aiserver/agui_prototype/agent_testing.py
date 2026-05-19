import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

import httpx
from mbai.base.base_ai_controller import BaseAIController
from mbai.base.model import PromptTemplate, RetryConfig
from mbai.base.oauth.oauth_helper import OAuthHelper
from openai import AsyncOpenAI
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPServerStreamableHTTP
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mbai.aiserver.config import build_mb_connection_values
from mbai.aiserver.mcp_helpers import get_mcp_via_http_streamable

mb_conn_values = build_mb_connection_values()

logger = logging.getLogger(__name__)


class LoggingTransport(httpx.AsyncBaseTransport):
    def __init__(self):
        self._transport = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        DO_PRINT = False
        if DO_PRINT:
            print("--- REQUEST ---")
            print(f"URL: {request.url}")
            print(f"Method: {request.method}")
            print(f"Headers: {dict(request.headers)}")
            print(f"Content type: {type(request.content)}")
            print(request.content.decode("utf-8"))
            print(f"Stream: {request.stream}")
            print("--- END ---", flush=True)
        print(request.content.decode("utf-8"))
        return await self._transport.handle_async_request(request)


def create_model():
    token = OAuthHelper.get_oauth_token_via_keycloak_values(mb_conn_values.inspire_keycloak)
    transport = LoggingTransport()
    http_client = httpx.AsyncClient(transport=transport)
    client = AsyncOpenAI(
        base_url="https://frontend-mb-oblivation-development.apps.openshift.sq.fabasoft.com/search/api/openai.v1.chat.completions.create/v1",
        api_key="unused",  # required by openai SDK but can be a placeholder
        default_headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "X-Username": mb_conn_values.x_username,
        },
        http_client=http_client,
    )

    model = OpenAIChatModel(
        "mistral-llm",
        provider=OpenAIProvider(openai_client=client),
    )

    return model


def get_mcp() -> MCPServerStreamableHTTP:
    # server = MCPServerStreamableHTTP("http://localhost:8001/mcp", http_client=http_client_mcp_jwt)
    server, url = get_mcp_via_http_streamable()
    return server


from pydantic_ai.models.test import TestModel


async def main():

    FALLBACK = TestModel(custom_output_text="[LLM unavailable — fallback response]")

    async def get_model():
        try:
            # Quick health check against your self-hosted endpoint
            res = BaseAIController(mb_conn_values, RetryConfig(retries=0)).llm_call_via_post_request(
                user_prompt=PromptTemplate(prompt_template="are you here?"),
                llm_url=mb_conn_values.get_frontend_completion_url(),
                model="mistral-llm",
                raise_on_error=True,
            )
            print("model works", res.output)
            return create_model()
        except Exception:
            print("using Fallback")
            return FALLBACK

    model = await get_model()
    agent = Agent(model=model)

    # model = create_model()

    # --- Dependencies (injected at runtime, great for DB connections, config, etc.) ---
    @dataclass
    class Deps:
        user_name: str

    # --- Structured output ---
    class OrderResponse(BaseModel):
        answer: str

    agent = Agent(model=model, deps_type=Deps, toolsets=[get_mcp()])

    @agent.tool_plain()
    def read_file(filename: str):
        """
        This tool is to read a file that the user uploaded. Only use this Tool when the user input needs the file content.
        DO NOT use the tool when the user just wants to copy the file or access the metadata
        Args: filename
        """
        file_path = Path(__file__).parent / "upload" / filename
        text = file_path.read_text()
        return text

    user_input = [
        "What is the main content of this document?",
        # "what type of document is it ?",
        "## FILE UPLOAD ## \n\n " + json.dumps({"filename": "test_file.txt", "filetype": "text"}),
    ]

    result = await agent.run(user_input)

    result.new_messages_json()

    print("---------------------- result -----------------------\n")
    print(result.output)

    print("----------------------- log -------------------------")
    # summarize_run(result)


if __name__ == "__main__":
    asyncio.run(main())
