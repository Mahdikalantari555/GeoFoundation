"""Unit tests for the NumpyBackend fallback retrieval backend."""

from __future__ import annotations

from geomemory.core.models import IndexRecord, SearchRequest
from geomemory.index.numpy_backend import NumpyBackend


def _record(id: str, text: str) -> IndexRecord:
    return IndexRecord(id=id, text=text, space_id="text.numpy.v1")


class TestNumpyBackend:
    def test_upsert_and_count(self):
        backend = NumpyBackend()
        backend.upsert([_record("a", "crop stress detection with NDVI")])
        backend.upsert([_record("b", "land cover classification")])
        assert backend.count() == 2

    def test_upsert_replaces(self):
        backend = NumpyBackend()
        backend.upsert([_record("a", "first")])
        backend.upsert([_record("a", "second")])
        assert backend.count() == 1

    def test_delete(self):
        backend = NumpyBackend()
        backend.upsert([_record("a", "x"), _record("b", "y")])
        backend.delete(["a"])
        assert backend.count() == 1

    def test_search_ranks_relevant(self):
        backend = NumpyBackend()
        backend.upsert(
            [
                _record("a", "crop stress detection using NDVI vegetation index"),
                _record("b", "the weather in paris is rainy today"),
            ]
        )
        hits = backend.search(SearchRequest(query="crop stress NDVI", top_k=5))
        assert len(hits) > 0
        assert hits[0].id == "a"
        assert hits[0].dense_score is not None

    def test_search_empty(self):
        backend = NumpyBackend()
        assert backend.search(SearchRequest(query="anything", top_k=5)) == []

    def test_search_empty_query(self):
        backend = NumpyBackend()
        backend.upsert([_record("a", "some text")])
        hits = backend.search(SearchRequest(query="", top_k=5))
        assert hits == []

    def test_from_database(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        temp_workspace.ingest(sample_markdown, collection_id=col.id)
        backend = NumpyBackend.from_database(temp_workspace.conn)
        assert backend.count() > 0
