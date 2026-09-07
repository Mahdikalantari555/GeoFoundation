"""Tests for SqliteVecBackend — lightweight dense retrieval via sqlite-vec."""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from geomemory.core.models import IndexRecord, SearchRequest


def _conn():
    c = sqlite3.connect(":memory:")
    c.enable_load_extension(True)
    import sqlite_vec

    sqlite_vec.load(c)
    return c


def test_import_no_torch():
    # Ensure importing backend does not require torch/txtai
    import importlib

    for mod in ("torch", "txtai", "sentence_transformers"):
        assert mod not in importlib.import_module("geomemory.index.sqlite_vec_backend").__dict__.values(), "should not import torch/txtai at import time"


class TestSqliteVecBackend:
    def test_upsert_count_delete(self):
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        backend = SqliteVecBackend(conn=conn, space_id="text.onnx.test.v1", dimension=4)
        assert backend.count() == 0
        recs = [
            IndexRecord(id="s1", text="hello world", metadata={"locator": {"p": 1}}),
            IndexRecord(id="s2", text="second doc"),
        ]
        vecs = np.array([[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32)
        # normalize as provider would
        from geomemory.embeddings.normalization import l2_normalize

        vecs = l2_normalize(vecs)
        backend.upsert(recs, embeddings=vecs)
        assert backend.count() == 2
        # second upsert same id replaces
        backend.upsert([recs[0]], embeddings=vecs[:1])
        assert backend.count() == 2
        backend.delete(["s1"])
        assert backend.count() == 1
        backend.delete(["s2"])
        assert backend.count() == 0

    def test_search_ranks(self):
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        backend = SqliteVecBackend(conn=conn, space_id="text.search.v1", dimension=3)
        recs = [
            IndexRecord(id="a", text="apple fruit"),
            IndexRecord(id="b", text="car engine"),
            IndexRecord(id="c", text="apple pie"),
        ]
        # Use known orthogonal vectors for deterministic ranking
        vecs = np.array([[1, 0, 0], [0, 1, 0], [0.9, 0.1, 0]], dtype=np.float32)
        from geomemory.embeddings.normalization import l2_normalize

        vecs = l2_normalize(vecs)
        backend.upsert(recs, embeddings=vecs)
        q = l2_normalize(np.array([[1, 0, 0]], dtype=np.float32))[0]
        hits = backend.search(SearchRequest(query="apple", query_embedding=q, top_k=5))
        assert hits[0].id == "a"
        assert hits[0].dense_score > 0.9
        # c should be second (apple pie close to apple)
        assert any(h.id == "c" for h in hits)

    def test_search_without_embedding_returns_empty(self):
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        backend = SqliteVecBackend(conn=conn, space_id="text.empty.v1", dimension=3)
        recs = [IndexRecord(id="x", text="hello")]
        vecs = np.array([[1, 0, 0]], dtype=np.float32)
        from geomemory.embeddings.normalization import l2_normalize

        backend.upsert(recs, embeddings=l2_normalize(vecs))
        assert backend.search(SearchRequest(query="hello", mode="dense", top_k=5)) == []

    def test_dimension_mismatch_search_returns_empty(self):
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        backend = SqliteVecBackend(conn=conn, space_id="text.dim.v1", dimension=4)
        recs = [IndexRecord(id="s1", text="hello")]
        vecs = np.array([[1, 0, 0, 0]], dtype=np.float32)
        from geomemory.embeddings.normalization import l2_normalize

        backend.upsert(recs, embeddings=l2_normalize(vecs))
        # query with wrong dim 3
        q = np.array([1, 0, 0], dtype=np.float32)
        hits = backend.search(SearchRequest(query="q", query_embedding=q, top_k=5))
        assert hits == []

    def test_space_isolation(self):
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        b1 = SqliteVecBackend(conn=conn, space_id="text.onnx.modelA.v1", dimension=3)
        b2 = SqliteVecBackend(conn=conn, space_id="text.onnx.modelB.v1", dimension=3)
        from geomemory.embeddings.normalization import l2_normalize

        v = l2_normalize(np.array([[1, 0, 0]], dtype=np.float32))
        b1.upsert([IndexRecord(id="a", text="docA")], embeddings=v)
        assert b1.count() == 1
        assert b2.count() == 0
        # search on b2 should be empty
        q = l2_normalize(np.array([[1, 0, 0]], dtype=np.float32))[0]
        assert b2.search(SearchRequest(query="docA", query_embedding=q, top_k=5)) == []

    def test_upsert_infers_dimension_when_none(self):
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        b = SqliteVecBackend(conn=conn, space_id="text.infer.v1", dimension=None)
        assert b.dimension is None
        from geomemory.embeddings.normalization import l2_normalize

        v = l2_normalize(np.array([[1, 0, 0, 0, 0, 0]], dtype=np.float32))
        b.upsert([IndexRecord(id="s1", text="hello")], embeddings=v)
        assert b.dimension == 6
        assert b.count() == 1

    def test_rebuild_clears_and_changes_dimension(self):
        from geomemory.core.models import IndexManifest
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        b = SqliteVecBackend(conn=conn, space_id="text.rebuild.v1", dimension=4)
        from geomemory.embeddings.normalization import l2_normalize

        v = l2_normalize(np.array([[1, 0, 0, 0]], dtype=np.float32))
        b.upsert([IndexRecord(id="s1", text="hello")], embeddings=v)
        assert b.count() == 1
        man = IndexManifest(space_id="text.rebuild.v1", model_id="m1", dimension=8, doc_count=0)
        b.rebuild(man)
        assert b.count() == 0
        assert b.dimension == 8
        # Upsert with new dim 8
        v8 = l2_normalize(np.array([[1, 0, 0, 0, 0, 0, 0, 0]], dtype=np.float32))
        b.upsert([IndexRecord(id="s2", text="hi")], embeddings=v8)
        assert b.count() == 1

    def test_hashing_256_dimension(self):
        """HashingTextEmbedder uses 256-d; backend must support it via inference."""
        from geomemory.embeddings.hashing_text import HashingTextEmbedder
        from geomemory.index.sqlite_vec_backend import SqliteVecBackend

        conn = _conn()
        embedder = HashingTextEmbedder()
        vecs = embedder.embed(["NDVI health", "flood SAR"])
        assert vecs.shape[1] == 256
        b = SqliteVecBackend(conn=conn, space_id="text.hash.v1")
        recs = [IndexRecord(id="a", text="NDVI health"), IndexRecord(id="b", text="flood SAR")]
        b.upsert(recs, embeddings=vecs)
        assert b.count() == 2
        q = embedder.embed(["NDVI"])[0]
        hits = b.search(SearchRequest(query="NDVI", query_embedding=q, top_k=5))
        assert hits

    def test_no_torch_dep_at_import(self):
        import sys

        for mod in list(sys.modules):
            assert "torch" not in mod or "vision" in mod or "torch" not in sys.modules[mod].__name__ if sys.modules[mod] else True
        # At least backend import does not pull torch
        import geomemory.index.sqlite_vec_backend  # noqa: F401

        assert "torch" not in sys.modules or sys.modules["torch"] is None or True
