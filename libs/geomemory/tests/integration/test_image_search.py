"""Integration tests for vision embedding and the image index (experimental)."""

from __future__ import annotations

import numpy as np
import pytest

from geomemory.core.exceptions import ModelNotLoadedError
from geomemory.embeddings.llama_cpp_vision import LlamaCppVisionEmbedder
from geomemory.embeddings.vision_embedder import PlaceholderVisionEmbedder
from geomemory.index.image_index import ImageIndex
from geomemory.index.manifest import create_manifest


class TestPlaceholder:
    def test_placeholder_raises_model_not_loaded(self):
        embedder = PlaceholderVisionEmbedder()
        assert embedder.space_id == "image.olmoearth.v1"
        with pytest.raises(ModelNotLoadedError):
            embedder.embed_images([b"\x89PNG"])

    def test_placeholder_embed_texts_none(self):
        assert PlaceholderVisionEmbedder().embed_texts(["a"]) is None


class TestLlamaCppVision:
    def test_raises_when_no_model_path(self):
        embedder = LlamaCppVisionEmbedder("")
        with pytest.raises(ModelNotLoadedError):
            embedder.embed_images([b"\x89PNG"])

    def test_raises_when_backend_missing(self, monkeypatch):
        import sys

        monkeypatch.setitem(sys.modules, "llama_cpp", None)
        embedder = LlamaCppVisionEmbedder("/models/olmoearth.gguf")
        with pytest.raises(ModelNotLoadedError):
            embedder.embed_images([b"\x89PNG"])

    def test_embed_texts_unsupported(self):
        assert LlamaCppVisionEmbedder("/models/x.gguf").embed_texts(["a"]) is None


class TestImageIndex:
    def test_upsert_search_roundtrip(self):
        index = ImageIndex()
        index.upsert("tile_a", np.array([1.0, 0.0, 0.0]))
        index.upsert("tile_b", np.array([0.0, 1.0, 0.0]))
        assert index.count() == 2
        results = index.search(np.array([1.0, 0.0, 0.0]), top_k=2)
        assert results[0]["target_id"] == "tile_a"
        assert results[0]["score"] == pytest.approx(1.0, abs=1e-5)

    def test_delete(self):
        index = ImageIndex(embeddings={"a": np.array([1.0, 0.0])})
        index.delete("a")
        assert index.count() == 0

    def test_search_empty(self):
        assert ImageIndex().search(np.array([1.0, 0.0])) == []

    def test_save_and_load(self, tmp_path):
        index = ImageIndex()
        index.upsert("tile_a", np.array([1.0, 0.0]))
        manifest = create_manifest(space_id="image.olmoearth.v1", model_id="olmoearth", dimension=2)
        index.save(tmp_path / "idx", manifest)
        loaded = ImageIndex.load(tmp_path / "idx")
        assert loaded.count() == 1
        assert loaded.ids() == ["tile_a"]


class TestWorkspaceImageSearch:
    def test_search_images_returns_results_when_index_built(self, temp_workspace):
        ws = temp_workspace
        index = ImageIndex()
        index.upsert("tile_x", np.array([1.0, 0.0, 0.0]))
        manifest = create_manifest(space_id="image.olmoearth.v1", model_id="olmoearth", dimension=3)
        index.save(ws.index_dir / "image", manifest)
        results = ws.search_images(np.array([1.0, 0.0, 0.0]))
        assert len(results) == 1
        assert results[0]["target_id"] == "tile_x"

    def test_search_images_returns_empty_without_index(self, temp_workspace):
        assert temp_workspace.search_images(np.array([1.0, 0.0])) == []
