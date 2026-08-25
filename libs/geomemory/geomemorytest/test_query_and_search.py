"""Tests for the SearchService query-plan pipeline."""
from __future__ import annotations

from geomemory.core.models import SearchHit, SearchResult
from geomemory.retrieval.query_parser import QueryParser
from geomemory.retrieval.search_service import SearchService


class _FakeBackend:
    def __init__(self, hits):
        self._hits = hits
        self.space_id = "fake.space.v1"

    def search(self, request):
        return self._hits


class TestSearchServicePipeline:
    def setup_method(self):
        self.parser = QueryParser()

    def test_empty_query_returns_no_crash(self):
        svc = SearchService(backends=[], parser=self.parser)
        result = svc.search("")
        assert isinstance(result, SearchResult)
        assert result.hits == []

    def test_whitespace_query_returns_no_crash(self):
        svc = SearchService(backends=[], parser=self.parser)
        result = svc.search("   \t\n  ")
        assert result.hits == []

    def test_sparse_only_results(self):
        sparse_hits = [SearchHit(id="s1", score=0.9)]
        svc = SearchService(backends=[_FakeBackend(sparse_hits)], parser=self.parser)
        result = svc.search("query", mode="sparse")
        assert result.hits == sparse_hits

    def test_dense_only_results(self):
        dense_hits = [SearchHit(id="d1", score=0.95)]
        svc = SearchService(backends=[_FakeBackend(dense_hits)], parser=self.parser)
        result = svc.search("query", mode="dense")
        assert result.hits == dense_hits

    def test_hybrid_fuses_results(self):
        sparse_hits = [SearchHit(id="s1", score=0.8)]
        dense_hits = [SearchHit(id="d1", score=0.9)]
        svc = SearchService(
            backends=[_FakeBackend(sparse_hits), _FakeBackend(dense_hits)],
            parser=self.parser,
        )
        result = svc.search("query", mode="hybrid", top_n=5)
        assert len(result.hits) >= 1
        ids = {h.id for h in result.hits}
        assert "s1" in ids or "d1" in ids

    def test_top_n_limits_output(self):
        sparse_hits = [SearchHit(id=f"s{i}", score=float(i)) for i in range(20)]
        svc = SearchService(backends=[_FakeBackend(sparse_hits)], parser=self.parser)
        result = svc.search("query", mode="sparse", top_n=5)
        assert len(result.hits) <= 5

    def test_deduplication_removes_duplicate_ids(self):
        hits = [SearchHit(id="dup", score=1.0), SearchHit(id="dup", score=0.9)]
        svc = SearchService(backends=[_FakeBackend(hits)], parser=self.parser)
        result = svc.search("query", mode="sparse")
        ids = [h.id for h in result.hits]
        assert ids.count("dup") <= 1

    def test_embedded_sensor_filter_forwarded(self):
        """Queries with embedded filters should still resolve and search."""
        svc = SearchService(backends=[_FakeBackend([])], parser=self.parser)
        result = svc.search("sensor:Sentinel-2 NDVI")
        assert "NDVI" in result.query or "sensor" in result.query

    def test_latency_recorded(self):
        svc = SearchService(
            backends=[_FakeBackend([SearchHit(id="h1", score=1.0)])],
            parser=self.parser,
        )
        result = svc.search("query", mode="sparse")
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    def test_result_has_query_plan(self):
        svc = SearchService(backends=[], parser=self.parser)
        result = svc.search("explain NDVI")
        assert result.query_plan is not None
