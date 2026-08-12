"""Integration tests for hybrid search over an ingested workspace."""

from __future__ import annotations

import hashlib


class TestHybridSearch:
    def test_search_finds_ingested_content(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)

        for query in ("NDVI crop stress", "classification accuracy", "remote sensing"):
            result = temp_workspace.search(query)
            assert result.total_hits > 0, f"no hits for {query!r}"

    def test_sparse_mode(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        result = temp_workspace.search("Sentinel-2", mode="sparse")
        assert result.total_hits > 0

    def test_dense_mode(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        result = temp_workspace.search("NDVI", mode="dense")
        assert result.total_hits > 0

    def test_collection_scoping(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        result = temp_workspace.search("NDVI", collections=[col.id])
        assert result.total_hits > 0
        scoped = temp_workspace.search("NDVI", collections=["missing"])
        assert scoped.hits == []

    def test_top_n_bounds_results(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        result = temp_workspace.search("NDVI Sentinel", top_n=1)
        assert len(result.hits) <= 1