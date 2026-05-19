"""Tool definitions for the Fabasoft chat agent.

Each tool is registered via `register_tools(agent, mb_conn_values)` so the
agent construction stays in `agent.py` and tool bodies stay here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from mbai.base.base_ai_controller import BaseAIController
from mbai.base.model import ControllerResponse
from pydantic_ai import Agent

if TYPE_CHECKING:
    from mbai.base.model import MBConnectionValues

# Upload directory — shared with the /upload route in aiserver.
# Kept as a module-level constant so tools can find files written by uploads.
_AISERVER_DIR = Path(__file__).parent.parent / "aiserver"
_UPLOAD_DIR = _AISERVER_DIR / "agui_prototype" / "upload"


def register_tools(agent: Agent, mb_conn_values: "MBConnectionValues") -> None:
    """Register all Fabi tools on the given agent.

    Called once during agent construction. `mb_conn_values` is captured
    in closures for tools that need backend access (vector search).
    """

    @agent.tool_plain
    def read_file(filename: str) -> str:
        """
        This tool is to read a file that the user uploaded. Only use this Tool
        when the user input needs the file content.
        DO NOT use the tool when the user just wants to copy the file or
        access the metadata.

        Args:
            filename: name of the uploaded file
        """
        file_path = _UPLOAD_DIR / filename
        return file_path.read_text()

    @agent.tool_plain
    def list_teamrooms() -> str:
        """
        This tool lists all teamrooms. A teamroom is a Document-Collection
        in the Fabasphere.
        """
        return json.dumps(
            {
                "teamrooms": [
                    {"name": "Teamroom Animals", "id": "trm_animals"},
                    {"name": "Teamroom Continents", "id": "trm_continents"},
                    {"name": "Teamroom People", "id": "trm_people"},
                ]
            }
        )

    @agent.tool_plain
    def copy_file_to_teamroom(filename: str, teamroom_id: str) -> dict:
        """
        This tool copies a file to a teamroom.

        Args:
            filename: name of the file
            teamroom_id: Valid id of a teamroom — get the existing teamrooms
                         by searching for them with `list_teamrooms`.
        """
        if teamroom_id not in {"trm_animals", "trm_continents", "trm_people"}:
            raise KeyError(f"{teamroom_id} is invalid")
        return {"text": f"successfully, copied file {filename} to teamroom {teamroom_id}"}

    @agent.tool_plain
    async def do_vector_search(query: str) -> list[str]:
        """Search the vector store for relevant content. Focusing on all kinds
        of information surrounding the Fabasoft company.

        Args:
            query: Make one nice query for a vector search using at least 5
                   words. Do not use the user_input directly but rewrite it.
        """
        result: ControllerResponse = BaseAIController(mb_conn_values).vector_search(
            queries=[query],
            k=10,
            minscore=0.1,
            resolve_overlaps=True,
            constraint=None,
            raise_on_error=True,
        )
        return [x["content"]["snippet_md"] for x in result.output]