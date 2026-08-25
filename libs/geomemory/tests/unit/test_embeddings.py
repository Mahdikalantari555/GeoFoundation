"""Tests for embedding normalization and adapters."""

from __future__ import annotations

import numpy as np

from geomemory.embeddings.normalization import cosine_similarity, l2_normalize


class TestNormalization:
    def test_l2_normalize_unit_norm(self):
        v = l2_normalize(np.array([[3.0, 4.0]], dtype=np.float32))
        assert np.isclose(np.linalg.norm(v), 1.0)

    def test_l2_normalize_zero_vector(self):
        v = l2_normalize(np.array([[0.0, 0.0]], dtype=np.float32))
        assert np.allclose(v, [[0.0, 0.0]])
        assert not np.isnan(v).any()

    def test_cosine_similarity_identical(self):
        a = np.array([[1.0, 0.0]])
        b = np.array([[2.0, 0.0]])
        assert np.isclose(cosine_similarity(a, b)[0], 1.0)

    def test_cosine_similarity_orthogonal(self):
        a = np.array([[1.0, 0.0]])
        b = np.array([[0.0, 1.0]])
        assert np.isclose(cosine_similarity(a, b)[0], 0.0)


class TestLlamaCppAdapterImport:
    def test_importable(self):
        import geomemory.embeddings.llama_cpp_text as mod

        assert hasattr(mod, "LlamaCppTextEmbedder")


class TestTextEmbedderProtocol:
    def test_has_protocol(self):
        from geomemory.embeddings.text_embedder import TextEmbedder

        assert TextEmbedder is not None
