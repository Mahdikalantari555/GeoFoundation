"""Tests for QdrantBackend with an in-process fake qdrant client."""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass

import numpy as np
import pytest

from geomemory.core.models import IndexRecord, SearchRequest
from geomemory.index.qdrant_backend import QdrantBackend


@dataclass
class _FakePoint:
    id: str
    score: float
    payload: dict | None = None


@dataclass
class _FakeCollectionInfo:
    points_count: int = 0


class _FakeQdrantClient:
    """In-memory fake Qdrant client keyed by collection name."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self._collections: dict[str, dict[str, dict]] = {}

    def get_collections(self):
        return types.SimpleNamespace(
            collections=[types.SimpleNamespace(name=n) for n in self._collections]
        )

    def create_collection(self, collection_name, vectors_config):
        self._collections[collection_name] = {}

    def upsert(self, collection_name, points):
        store = self._collections.setdefault(collection_name, {})
        for p in points:
            store[p.id] = p.payload
            # Stash the raw vector for cosine scoring in search.
            store[p.id]["_vec"] = p.vector

    def search(self, collection_name, query_vector, limit, with_payload=True):
        store = self._collections.get(collection_name, {})
        # Score = cosine similarity approximated via dot product against stored vectors.
        q = np.asarray(query_vector, dtype=np.float32)
        q = q / (np.linalg.norm(q) + 1e-12)
        scored = []
        for pid, payload in store.items():
            vec = np.asarray(payload.get("_vec", [0.0, 0.0, 0.0, 0.0]), dtype=np.float32)
            vec = vec / (np.linalg.norm(vec) + 1e-12)
            score = float(np.dot(q, vec))
            scored.append(_FakePoint(id=pid, score=score, payload=payload))
        scored.sort(key=lambda s: s.score, reverse=True)
        # Stash the vector for delete-by-id resolution via payload.
        return scored[:limit]

    def delete(self, collection_name, points_selector):
        store = self._collections.get(collection_name, {})
        for pid in points_selector.points:
            store.pop(pid, None)

    def get_collection(self, collection_name):
        return _FakeCollectionInfo(points_count=len(self._collections.get(collection_name, {})))


@pytest.fixture()
def fake_qdrant(monkeypatch):
    pkg = types.ModuleType("qdrant_client")

    class _Client(_FakeQdrantClient):
        pass

    pkg.QdrantClient = _Client
    http_mod = types.ModuleType("qdrant_client.http")
    models_mod = types.SimpleNamespace(
        VectorParams=types.SimpleNamespace,
        Distance=types.SimpleNamespace(COSINE="cosine"),
        PointStruct=types.SimpleNamespace,
        PointIdsList=types.SimpleNamespace,
    )
    http_mod.models = models_mod
    sys.modules["qdrant_client"] = pkg
    sys.modules["qdrant_client.http"] = http_mod
    sys.modules["qdrant_client.http.models"] = models_mod
    # Build proper constructors used by QdrantBackend.
    models_mod.VectorParams = lambda size, distance: types.SimpleNamespace(
        size=size, distance=distance
    )
    models_mod.PointStruct = lambda id, vector, payload: types.SimpleNamespace(
        id=id, vector=vector, payload=payload
    )
    models_mod.PointIdsList = lambda points: types.SimpleNamespace(points=points)
    return pkg


class TestQdrantBackend:
    def _backend(self, space_id="text.st.x.v1", **kw):
        return QdrantBackend(space_id, url="http://fake:6333", **kw)

    def test_upsert_and_count(self, fake_qdrant):
        backend = self._backend()
        backend.upsert(
            [IndexRecord(id="s1", text="NDVI"), IndexRecord(id="s2", text="flood")],
            embeddings=np.array(
                [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]],
                dtype=np.float32,
            ),
        )
        assert backend.count() == 2

    def test_upsert_idempotent(self, fake_qdrant):
        backend = self._backend()
        backend.upsert(
            [IndexRecord(id="s1", text="v1")],
            embeddings=np.array([[1.0, 0.0, 0.0, 0.0]]),
        )
        backend.upsert(
            [IndexRecord(id="s1", text="v2")],
            embeddings=np.array([[1.0, 0.0, 0.0, 0.0]]),
        )
        assert backend.count() == 1

    def test_search_top_k_and_ordering(self, fake_qdrant):
        backend = self._backend()
        backend.upsert(
            [
                IndexRecord(id="s1", text="vegetation"),
                IndexRecord(id="s2", text="flood"),
                IndexRecord(id="s3", text="urban"),
            ],
            embeddings=np.array(
                [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]],
                dtype=np.float32,
            ),
        )
        request = SearchRequest(
            query="vegetation",
            query_embedding=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            mode="dense",
            top_k=2,
            top_n=2,
        )
        hits = backend.search(request)
        assert len(hits) <= 2
        # The query is closest to s1.
        assert hits[0].id == "s1"

    def test_delete_removes_hits(self, fake_qdrant):
        backend = self._backend()
        backend.upsert(
            [IndexRecord(id="s1", text="a"), IndexRecord(id="s2", text="b")],
            embeddings=np.array([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]], dtype=np.float32),
        )
        backend.delete(["s1"])
        assert backend.count() == 1

    def test_cross_space_isolation(self, fake_qdrant):
        a = self._backend(space_id="text.st.a.v1")
        b = self._backend(space_id="text.st.b.v1")
        a.upsert(
            [IndexRecord(id="s1", text="a")],
            embeddings=np.array([[1.0, 0.0, 0.0, 0.0]]),
        )
        b.upsert(
            [IndexRecord(id="s2", text="b")],
            embeddings=np.array([[0.0, 1.0, 0.0, 0.0]]),
        )
        req = SearchRequest(
            query="x",
            query_embedding=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32),
            mode="dense",
            top_k=5,
        )
        hits_a = a.search(req)
        assert all(h.id != "s2" for h in hits_a)

    def test_missing_extra_message(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "qdrant_client", None)
        backend = self._backend()
        with pytest.raises(ImportError, match=r"\[vector\]"):
            backend.upsert(
            [IndexRecord(id="s1", text="a")],
            embeddings=np.array([[1.0, 0.0, 0.0, 0.0]]),
        )
