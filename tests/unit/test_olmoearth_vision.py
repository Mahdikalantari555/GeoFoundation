"""Tests for the OLMoEarth v1.2 Nano torch-native vision embedder.

These tests use the real ``olmoearth_pretrain`` model loader when available.
They skip gracefully if the ``vision`` extra or a real checkpoint is not
present, so the core package stays installable without torch.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

# Path to a real OLMoEarth v1.2 Nano checkpoint, provided via env for local runs.
VISION_PATH = os.environ.get("GEOMEMORY_TEST_VISION_PATH")

torch_available = False
olmoearth_available = False
try:
    import torch  # noqa: F401

    torch_available = True
    import olmoearth_pretrain  # noqa: F401

    olmoearth_available = True
except ImportError:
    pass

needs_vision = pytest.mark.skipif(
    not (torch_available and olmoearth_available and VISION_PATH),
    reason="requires [vision] extra and GEOMEMORY_TEST_VISION_PATH",
)


@pytest.fixture
def embedder():
    from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

    return OlmoEarthVisionEmbedder(VISION_PATH)


class TestContractWithoutModel:
    """Contract checks that do not require a real checkpoint."""

    def test_space_id_prefix(self) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        assert OlmoEarthVisionEmbedder("dummy").space_id == "image.olmoearth-nano-v12.v1"
        assert OlmoEarthVisionEmbedder("dummy").space_id.startswith("image.")

    def test_embed_texts_returns_none(self) -> None:
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        assert OlmoEarthVisionEmbedder("dummy").embed_texts(["hello"]) is None

    def test_missing_checkpoint_error_names_path(self, tmp_path: Path) -> None:
        from geomemory.core.exceptions import ModelNotLoadedError
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder

        missing = tmp_path / "nonexistent.pth"
        emb = OlmoEarthVisionEmbedder(str(missing))
        with pytest.raises(ModelNotLoadedError) as exc_info:
            emb._load()
        assert str(missing) in str(exc_info.value)


class TestRealCheckpoint:
    """Behavioural tests against a real OLMoEarth Nano checkpoint."""

    @needs_vision
    def test_load_dim(self, embedder) -> None:
        model = embedder._load()
        assert model is not None

    @needs_vision
    def test_embed_shape_dtype_l2norm(self, embedder) -> None:
        images = [np.random.RandomState(i).rand(32, 32, 3).astype(np.float32) for i in range(3)]
        result = embedder.embed_images(images)
        assert result.shape == (3, 128)
        assert result.dtype == np.float32
        norms = np.linalg.norm(result, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)

    @needs_vision
    def test_embed_empty_list(self, embedder) -> None:
        result = embedder.embed_images([])
        assert result.shape == (0, 128)

    @needs_vision
    def test_semantic_similarity_ordering(self, embedder) -> None:
        """Near-duplicate inputs should be more similar than random inputs."""
        rng = np.random.RandomState(0)
        base = rng.rand(64, 64, 3).astype(np.float32)
        noisy = np.clip(base + rng.rand(64, 64, 3).astype(np.float32) * 0.02, 0, 1)
        other = rng.rand(64, 64, 3).astype(np.float32)

        e_base = embedder.embed_images([base])[0]
        e_noisy = embedder.embed_images([noisy])[0]
        e_other = embedder.embed_images([other])[0]

        cos = lambda a, b: float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
        assert cos(e_base, e_noisy) > cos(e_base, e_other)

    @needs_vision
    def test_pil_and_path_inputs(self, embedder, tmp_path: Path) -> None:
        from PIL import Image

        arr = np.random.RandomState(1).rand(48, 48, 3).astype(np.float32)
        img = Image.fromarray((arr * 255).astype(np.uint8))
        p = tmp_path / "img.png"
        img.save(p)

        from pathlib import Path as _P

        r_path = embedder.embed_images([str(p)])[0]
        r_pil = embedder.embed_images([img])[0]
        cos = float(np.dot(r_path, r_pil) / (np.linalg.norm(r_path) * np.linalg.norm(r_pil)))
        assert cos > 0.99  # same image -> same embedding
