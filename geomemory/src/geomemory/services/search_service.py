"""Search service — orchestrates retrieval backends."""

from __future__ import annotations

from geomemory.core.models import SearchFilters, SearchResult
from geomemory.retrieval.search_service import SearchService as RetrievalSearchService


class SearchService:
    """Public search entry point wrapping the retrieval search service."""

    def __init__(self, retrieval: RetrievalSearchService) -> None:
        self.retrieval = retrieval

    def search(
        self,
        query: str,
        *,
        mode: str = "hybrid",
        top_k: int = 20,
        top_n: int = 5,
        filters: SearchFilters | None = None,
    ) -> SearchResult:
        """Execute a hybrid search."""
        return self.retrieval.search(
            query,
            mode=mode,
            top_k=top_k,
            top_n=top_n,
            filters=filters,
        )