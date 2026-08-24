"""Tests for SentenceTransformerEmbedder with a stubbed sentence_transformers module."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
import types

import numpy as np
import pytest

from geomemory.core.models import WorkspaceSettings
from geomemory.embeddings.hashing_text import HashingTextEmbedder
from geomemory.embeddings.llama_cpp_text import LlamaCppTextEmbedder
from geomemory.embeddings.sentence_transformer import SentenceTransformerEmbedder
from geomemory.services.index_service import IndexService


class _FakeSTModel:
    """Stub sentence-transformers model emitting deterministic vectors."""

    def __init__(self, model_name):
        self.model_name = model_name

    def encode(self, texts, normalize_embeddings=False):
        vecs = []
        for t in texts:
            h = hash(t) % 1000
            vecs.append(
                np.array(
                    [float(len(t)), float(h % 100), float(h % 50), float(h % 10)],
                    dtype=np.float32,
                )
            )
        return np.stack(vecs)


@pytest.fixture()
def fake_st(monkeypatch):
    """Provide a fake sentence_transformers package."""
    pkg = types.ModuleType("sentence_transformers")

    def _init(self, model_name):
        self._fake = _FakeSTModel(model_name)

    def _encode(self, texts, normalize_embeddings=False):
        return self._fake.encode(texts, normalize_embeddings=normalize_embeddings)

    cls = type("SentenceTransformer", (), {"__init__": _init, "encode": _encode})
    pkg.SentenceTransformer = cls
    monkeypatch.setitem(sys.modules, "sentence_transformers", pkg)
    return pkg


def _st_service():
    tmp = tempfile.mkdtemp()
    return IndexService(sqlite3.connect(":memory:"), tmp)


class TestSentenceTransformerEmbedder:
    def test_space_id_stability_and_divergence(self, fake_st):
        st = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        assert st.space_id == "text.st.sentence-transformers-all-MiniLM-L6-v2.v1"
        assert st.space_id != HashingTextEmbedder().space_id
        assert st.space_id != LlamaCppTextEmbedder("/tmp/m.gguf").space_id

    def test_space_id_different_model_differs(self, fake_st):
        a = SentenceTransformerEmbedder("intfloat/multilingual-e5-base")
        b = SentenceTransformerEmbedder("BAAI/bge-m3")
        assert a.space_id != b.space_id

    def test_minilm_passthrough_no_prefix(self, fake_st):
        st = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        v_passage = st.embed(["hello world"])
        v_query = st.embed_query(["hello world"])
        # MiniLM family is 'generic' -> no prefix -> identical vectors.
        assert np.allclose(v_passage, v_query)

    def test_e5_prefix_differs_query_vs_passage(self, fake_st):
        st = SentenceTransformerEmbedder("intfloat/multilingual-e5-small")
        v_passage = st.embed(["hello world"])
        v_query = st.embed_query(["hello world"])
        # e5 family applies different prefixes -> vectors differ.
        assert not np.allclose(v_passage, v_query)

    def test_l2_normalized(self, fake_st):
        st = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        vecs = st.embed(["NDVI vegetation health", "flood mapping"])
        assert vecs.dtype == np.float32
        assert vecs.shape == (2, 4)
        assert np.allclose(np.linalg.norm(vecs, axis=1), 1.0)

    def test_embed_batch(self, fake_st):
        st = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2")
        vecs = st.embed_batch(["a", "b", "c"], batch_size=2)
        assert vecs.shape == (3, 4)

    def test_missing_extra_message(self, monkeypatch):
        # Simulate the optional package being absent; the error surfaces on load.
        monkeypatch.setitem(sys.modules, "sentence_transformers", None)
        s = _st_service()
        s._settings = WorkspaceSettings(name="ws", embedding_backend="sentence-transformers")
        with pytest.raises(ImportError, match=r"\[st\]"):
            s._embedder(None).embed(["hello"])
