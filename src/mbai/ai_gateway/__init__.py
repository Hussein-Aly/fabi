"""AI Gateway — cross-cutting concerns for every agent run.

Exports the `AIGateway` service and its outcome types. Sub-feature
modules (`guardrails/`, `usage/`) are also importable directly when
needed, but most callers should go through `AIGateway`.
"""

from mbai.ai_gateway.service import AIGateway, PreRunOutcome

__all__ = ["AIGateway", "PreRunOutcome"]