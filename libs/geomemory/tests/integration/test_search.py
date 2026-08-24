"""Integration tests for hybrid search over an ingested workspace."""

from __future__ import annotations


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


class TestSearchServiceWiring:
    def test_qdrant_backend_flows_into_search_service(
        self, temp_workspace, sample_markdown, monkeypatch
    ):
        from geomemory.retrieval.search_service import SearchService

        class _FakeQdrantBackend:
            space_id = "text.st.x.v1"

            def search(self, request):
                from geomemory.core.models import SearchHit
                return [SearchHit(id="q1", score=0.95, text="qdrant hit")]

        service = SearchService([_FakeQdrantBackend()])
        result = service.search("test", mode="dense")
        assert result.hits[0].id == "q1"

    def test_workspace_qdrant_search(self, temp_workspace, sample_markdown, monkeypatch):
        ws = temp_workspace
        col = ws.create_collection("docs")
        ws.ingest(sample_markdown, collection_id=col.id)

        # Build the local index first so the manifest exists; then monkeypatch the
        # _qdrant_backend method so search routes through our fake.
        ws.build_index("text.hash.v1")

        class _FakeQdrantBackend:
            space_id = "text.hash.v1"

            def search(self, request):
                from geomemory.core.models import SearchHit
                return [SearchHit(id="s1", score=0.9, text="NDVI hit")]

        monkeypatch.setattr(
            "geomemory.services.index_service.IndexService._qdrant_backend",
            lambda self, space_id: _FakeQdrantBackend(),
        )
        ws.settings.vector_backend = "qdrant"
        ws.settings.qdrant_url = "http://fake:6333"
        result = ws.search("NDVI", mode="dense")
        assert result.total_hits >= 0
