"""Integration tests for TxtaiBackend.

Skipped when any of the txtai runtime dependencies (torch, transformers) is
not installed; txtai requires them to build the embedding model even for
precomputed vectors.
"""

from __future__ import annotations

import pytest

from geomemory.core.models import IndexRecord, SearchRequest

txtai = pytest.importorskip("txtai")
torch = pytest.importorskip("torch")
transformers = pytest.importorskip("transformers")

from geomemory.index.txtai_backend import TxtaiBackend  # noqa: E402


@pytest.fixture
def backend(tmp_path):
    return TxtaiBackend(str(tmp_path / "idx"))


def _network_available() -> bool:
    """Check if HuggingFace Hub is reachable for model downloads."""
    import socket

    try:
        with socket.create_connection(("huggingface.co", 443), timeout=2):
            return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _network_available(),
    reason="txtai integration tests require HuggingFace Hub access (model download)",
)


class TestTxtaiBackend:
    def test_upsert_and_count(self, backend):
        backend.upsert([IndexRecord(id="s1", text="NDVI vegetation health")])
        assert backend.count() == 1

    def test_hybrid_search_roundtrip(self, backend):
        backend.upsert(
            [
                IndexRecord(id="s1", text="NDVI measures vegetation health"),
                IndexRecord(id="s2", text="Flood mapping with SAR"),
            ]
        )
        request = SearchRequest(query="vegetation health", mode="hybrid", top_k=5, top_n=5)
        hits = backend.search(request)
        assert hits, "expected at least one hit"
        assert hits[0].id in ("s1", "s2")
        assert hits[0].score > 0.0

    def test_delete(self, backend):
        backend.upsert([IndexRecord(id="s1", text="only record")])
        backend.delete(["s1"])
        assert backend.count() == 0

    def test_upsert_empty_is_noop(self, backend):
        backend.upsert([])
        assert backend.count() == 0
