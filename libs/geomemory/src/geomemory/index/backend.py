"""RetrievalBackend protocol and related interfaces."""

from __future__ import annotations

from typing import Protocol

from geomemory.core.models import IndexManifest, IndexRecord, SearchHit, SearchRequest


class RetrievalBackend(Protocol):
    """Protocol for pluggable retrieval backends.

    Implementations wrap vector index engines (e.g. txtai) or fallback
    implementations (e.g. numpy cosine similarity).
    """

    space_id: str

    def upsert(self, records: list[IndexRecord]) -> None:
        """Insert or update indexed records."""
        ...

    def search(self, request: SearchRequest) -> list[SearchHit]:
        """Execute a search and return ranked hits."""
        ...

    def delete(self, ids: list[str]) -> None:
        """Remove indexed records by id."""
        ...

    def rebuild(self, manifest: IndexManifest) -> None:
        """Rebuild the index from source of truth."""
        ...

    def count(self) -> int:
        """Return the number of indexed records."""
        ...
