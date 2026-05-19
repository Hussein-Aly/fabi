"""FastAPI dependency providers.

Things constructed once at app startup (in the lifespan) and exposed
to route handlers through FastAPI's typed `Depends` machinery. Tests
override these via `app.dependency_overrides`.

The actual construction happens in the lifespan in `api_server.py`.
This module is just the typed accessor layer.
"""

from __future__ import annotations

from fastapi import Request

from mbai.ai_gateway.service import AIGateway


def get_gateway(request: Request) -> AIGateway:
    """Return the AIGateway stored on `app.state` by the lifespan.

    Used as a route dependency:

        async def my_route(
            gateway: AIGateway = Depends(get_gateway),
        ): ...

    Override in tests:

        app.dependency_overrides[get_gateway] = lambda: test_gateway
    """
    return request.app.state.gateway