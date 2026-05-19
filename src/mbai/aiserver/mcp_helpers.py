import httpx
import requests
from pydantic_ai.mcp import MCPServerStreamableHTTP

DUMMY_JWT = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpc3MiOiJodHRwczovL3NvbG9ibGl2YXRpb25tYi5zcS5mYWJhc29mdC5jb20vZm9saW8iLCJzdWIiOiJzY2h1bGxlcjAwMDFAc3EuZmFiYXNvZnQuY29tIiwiYXVkIjoiYWktcHl0aG9uLXNlcnZpY2UiLCJleHAiOjE3NzczMDk3NTcsIm5iZiI6MTc3NzI5Nzc1NywiaWF0IjoxNzc3Mjk3NzU3LCJqdGkiOiJORmtoRk9ucTlxRkdveWtaS2QvbmVvNlgiLCJzY29wZSI6IkNPTy4xLjEwMDEuMS42MDg2MzMifQ.hbhgQM8NZq8X6C0RV2vn_mFKOwrVqsJJTn3MrI-4JTE"


def check_mcp_connection(url: str, timeout: int = 5) -> bool:
    """Check if MCP server is reachable."""
    try:
        response = requests.get(url, timeout=timeout)

        return "id" in response.json() and "error" in response.json()

    except Exception as e:
        print(e)
        return False


def check_mcp_connection(url: str, timeout: int = 5) -> bool:
    """Check if MCP server is reachable."""
    try:
        response = requests.get(url, timeout=timeout, headers={"Authorization": f"Bearer {DUMMY_JWT}"})
        return response.status_code == 405
    except Exception as e:
        print(e)
        return False


# Pass the http_client to the MCP server
# server = MCPServerStreamableHTTP(url="http://localhost:8000/mcp", http_client=http_client_mcp_jwt)


def get_mcp_url():
    print("connect to mcp")
    local_mcp_url = "http://localhost:8001/mcp"
    cloudevel_mcp_url = "http://fabidemoclouddevel.sq.fabasoft.com:8001/mcp"
    url = local_mcp_url if check_mcp_connection(local_mcp_url) else cloudevel_mcp_url
    print(f"use MCP server: {url}")
    return url


import json


async def log_request(request: httpx.Request):
    print("=" * 80)
    print(">>> MCP CLIENT REQUEST")
    print(f"    Method:  {request.method}")
    print(f"    URL:     {request.url}")
    print("    Headers:")
    for k, v in request.headers.items():
        print(f"        {k}: {v}")
    body = request.content.decode() if request.content else None
    if body:
        try:
            print("    Body:")
            print(json.dumps(json.loads(body), indent=4))
        except json.JSONDecodeError:
            print(f"    Body: {body}")
    print("-" * 80)


async def log_response(response: httpx.Response):
    await response.aread()
    print("<<< MCP CLIENT RESPONSE")
    print(f"    Status:  {response.status_code}")
    print("    Headers:")
    for k, v in response.headers.items():
        print(f"        {k}: {v}")
    body = response.text
    if body:
        try:
            print("    Body:")
            print(json.dumps(json.loads(body), indent=4))
        except json.JSONDecodeError:
            # SSE / streaming — print raw (truncated)
            print(f"    Body: {body[:2000]}")
    print("=" * 80)


def get_mcp_via_http_streamable() -> tuple[MCPServerStreamableHTTP, str]:

    url = get_mcp_url()
    # url = "http://localhost:8001/mcp"

    http_client_mcp_jwt = httpx.AsyncClient(
        headers={"Authorization": f"Bearer {DUMMY_JWT}"},
        timeout=30.0,
        # event_hooks={
        #    "request": [log_request],
        #    "response": [log_response],
        # },
    )
    server = MCPServerStreamableHTTP(url=url, http_client=http_client_mcp_jwt)
    return server, url


if __name__ == "__main__":
    check_mcp_connection("http://localhost:8001/mcp")
