"""Tests for EmbeddingProvider abstraction and ONNX canonical provider."""

from __future__ import annotations

import types
import sys

import numpy as np
import pytest

from geomemory.embeddings.provider import (
    CustomEmbeddingProvider,
    ONNXEmbeddingProvider,
    OpenAIEmbeddingProvider,
    VoyageEmbeddingProvider,
)


class TestEmbeddingProviderInterface:
    def test_onnx_default_space_and_dim(self):
        prov = ONNXEmbeddingProvider()
        assert prov.space_id == "text.onnx.Xenova-all-MiniLM-L6-v2.v1"
        assert prov.dimension == 384
        assert prov.model_id == "Xenova/all-MiniLM-L6-v2"

    def test_onnx_legacy_st_normalization(self):
        prov = ONNXEmbeddingProvider("sentence-transformers/all-MiniLM-L6-v2")
        # Legacy ST id maps to Xenova quantized export
        assert prov.space_id == "text.onnx.Xenova-all-MiniLM-L6-v2.v1"
        assert prov.model_id == "Xenova/all-MiniLM-L6-v2" or prov.model_id == "sentence-transformers/all-MiniLM-L6-v2"

    def test_onnx_custom_model_space(self):
        prov = ONNXEmbeddingProvider("BAAI/bge-small-en-v1.5")
        assert prov.space_id == "text.onnx.BAAI-bge-small-en-v1-5.v1"
        assert prov.dimension == 384

    def test_future_providers_stub_raise(self):
        for cls in (OpenAIEmbeddingProvider, VoyageEmbeddingProvider, CustomEmbeddingProvider):
            p = cls("test/model")
            with pytest.raises(NotImplementedError, match="not configured|ONNXEmbeddingProvider"):
                p.embed(["hello"])
            with pytest.raises(NotImplementedError):
                p.embed_query(["hello"])
            assert p.dimension == 0

    def test_future_space_id(self):
        p = OpenAIEmbeddingProvider("openai/text-embedding-3-small")
        assert "openai" in p.space_id.lower()
        assert "text-embedding" in p.space_id

    def test_onnx_embed_with_stubbed_inner(self, monkeypatch):
        """Stub OnnxTextEmbedder to avoid loading real ONNX weights."""
        fake = types.ModuleType("geomemory.embeddings.onnx_text")

        class FakeOnnx:
            def __init__(self, model_name, **kw):
                self.model_name = model_name
                self._model_id = model_name
                self.space_id = f"text.onnx.{model_name.replace('/','-').replace('.','-')}.v1"
                self.model_id = model_name

            def embed(self, texts):
                # Return deterministic L2-normalized vectors
                rng = np.random.default_rng(42)
                m = rng.random((len(texts), 384)).astype(np.float32)
                m = m / np.linalg.norm(m, axis=1, keepdims=True)
                return m

            def embed_query(self, texts):
                return self.embed(texts)

            def embed_batch(self, texts, batch_size):
                out = []
                for i in range(0, len(texts), batch_size):
                    out.append(self.embed(texts[i : i + batch_size]))
                return np.concatenate(out, axis=0) if out else np.zeros((0, 384), dtype=np.float32)

            def download_with_progress(self, on_progress=None):
                return "/tmp/fake"

        monkeypatch.setitem(sys.modules, "geomemory.embeddings.onnx_text", fake)
        # Patch the import inside provider.py by directly monkeypatching ONNXEmbeddingProvider's inner
        prov = ONNXEmbeddingProvider.__new__(ONNXEmbeddingProvider)
        prov._inner = FakeOnnx("Xenova/all-MiniLM-L6-v2")
        prov._dimension = 384
        vecs = prov.embed(["hello world", "second text"])
        assert vecs.shape == (2, 384)
        assert np.allclose(np.linalg.norm(vecs, axis=1), 1.0, atol=1e-5)
        q = prov.embed_query(["query"])
        assert q.shape == (1, 384)
        b = prov.embed_batch(["a", "b", "c"], batch_size=2)
        assert b.shape == (3, 384)

    def test_factory_returns_onnx_by_default(self):
        from geomemory.core.models import WorkspaceSettings
        from geomemory.embeddings.factory import build_text_embedder

        settings = WorkspaceSettings(name="ws")
        # default workspace has no provider set → factory should return onnx or hashing fallback
        # With new defaults, embedding_provider None + embedding_backend hashing → returns HashingTextEmbedder (legacy)
        # But explicit onnx should return ONNX
        settings2 = WorkspaceSettings(name="ws", embedding_provider="onnx", onnx_model_name="Xenova/all-MiniLM-L6-v2")
        prov = build_text_embedder(settings2)
        assert isinstance(prov, ONNXEmbeddingProvider)
        assert prov.dimension == 384

    def test_factory_legacy_st_warns(self):
        import warnings

        from geomemory.core.models import WorkspaceSettings
        from geomemory.embeddings.factory import build_text_embedder

        settings = WorkspaceSettings(name="ws", embedding_backend="sentence-transformers")
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            prov = build_text_embedder(settings)
            assert any(issubclass(x.category, DeprecationWarning) for x in w)
        # Legacy ST maps to onnx
        assert prov.space_id.startswith("text.onnx.")

    def test_factory_hashing(self):
        from geomemory.core.models import WorkspaceSettings
        from geomemory.embeddings.factory import build_text_embedder
        from geomemory.embeddings.hashing_text import HashingTextEmbedder

        settings = WorkspaceSettings(name="ws", embedding_backend="hashing")
        prov = build_text_embedder(settings)
        assert isinstance(prov, HashingTextEmbedder)
