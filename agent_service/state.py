from __future__ import annotations
from pydantic import BaseModel


class Document(BaseModel):
    id: str
    title: str
    content: str


class SearchResult(BaseModel):
    id: str
    title: str
    score: float


class DeletionResult(BaseModel):
    deleted_id: str
    success: bool


class DMSState(BaseModel):
    open_document: Document | None = None
    search_results: list[SearchResult] = []
    pending_confirmation: dict | None = None
    # pending_confirmation is frontend-only:
    # set when confirm_action ToolCallEvent is received,
    # cleared after the tool result is sent back.
