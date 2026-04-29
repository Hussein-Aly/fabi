from __future__ import annotations
from uuid import uuid4
from agent_service.state import Document, DeletionResult, SearchResult


class MockMCPClient:
    def __init__(self) -> None:
        self._store: dict[str, Document] = {}

    def create(self, title: str, content: str) -> Document:
        doc = Document(id=str(uuid4()), title=title, content=content)
        self._store[doc.id] = doc
        return doc

    def read(self, doc_id: str) -> Document:
        return self._store[doc_id]

    def update(self, doc_id: str, changes: dict) -> Document:
        doc = self._store[doc_id].model_copy(update=changes)
        self._store[doc_id] = doc
        return doc

    def delete(self, doc_id: str) -> DeletionResult:
        del self._store[doc_id]
        return DeletionResult(deleted_id=doc_id, success=True)

    def search(self, query: str) -> list[SearchResult]:
        return [
            SearchResult(id=k, title=v.title, score=1.0)
            for k, v in self._store.items()
            if query.lower() in v.title.lower()
        ]
