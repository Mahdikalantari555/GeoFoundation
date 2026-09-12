"""Integration tests for vision embedding during raster ingest (Track A)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


class MockEmbedder:
    """Fake OlmoEarthVisionEmbedder that does not require torch."""

    space_id = "image.olmoearth-nano-v12.v1"
    model_id = "olmoearth-nano-v1.2"

    def __init__(self, _: str) -> None:
        self._called = False

    @property
    def called(self) -> bool:
        return self._called

    def embed_images(self, images):  # type: ignore[no-untyped-def]
        self._called = True
        n = len(images) if images else 0
        return np.zeros((n, 128), dtype=np.float32)

    def embed_texts(self, texts):  # type: ignore[no-untyped-def]
        return None


def _make_tiff(tmp_path: Path) -> Path:
    """Create a minimal valid-ish GeoTIFF so the loader yields a scene."""
    tiff_path = tmp_path / "scene.tif"
    # Use a tiny PNG wrapped in a no-op bytes blob; the loader will fail on
    # a real parse but we only need to exercise the vision-embed path when
    # tiles have preview paths. For the success case we mock _parse_spatial_source.
    tiff_path.write_bytes(b"not-a-real-tiff")
    return tiff_path


class TestVisionIngest:
    def test_embed_images_called_when_vision_path_set(self, temp_workspace, monkeypatch):
        monkeypatch.setitem(sys.modules, "torch", MagicMock())
        monkeypatch.setitem(sys.modules, "olmoearth_pretrain", MagicMock())
        monkeypatch.setattr(
            "geomemory.embeddings.olmoearth_vision.OlmoEarthVisionEmbedder",
            MockEmbedder,
        )
        with patch.object(temp_workspace, "_parse_spatial_source") as mock_parse:
            mock_parse.return_value = (
                [],
                {
                    "scene": {
                        "title": "test",
                        "crs": "EPSG:4326",
                        "transform": [1.0, 0.0, 0.0, 0.0, -1.0, 0.0],
                        "bands": [{"name": b} for b in ("red", "nir", "swir")],
                        "dtype": "uint8",
                        "width": 512,
                        "height": 512,
                        "bbox": [0.0, 0.0, 1.0, 1.0],
                    },
                    "tiles": [
                        {
                            "window": {"x": 0, "y": 0, "width": 256, "height": 256},
                            "transform": [1.0, 0.0, 0.0, 0.0, -1.0, 0.0],
                            "preview_path": str(
                                (temp_workspace.path / "artifacts" / "tiles" / "tile_0.png")
                            ),
                        }
                    ],
                },
            )
            col = temp_workspace.create_collection("rs")
            tiff = temp_workspace.path / "dummy.tif"
            tiff.write_bytes(b"x")
            try:
                temp_workspace.update_settings(vision_path="/models/olmoearth")
                temp_workspace.ingest(tiff, col.id)
            finally:
                temp_workspace.update_settings(vision_path=None)

    def test_no_embed_when_vision_path_unset(self, temp_workspace):
        with patch("geomemory.ingest.vision_embed.try_embed_vision") as mock_embed:
            col = temp_workspace.create_collection("docs")
            src = temp_workspace.path / "empty.txt"
            src.write_text("hi")
            temp_workspace.ingest(src, col.id)
            mock_embed.assert_not_called()

    def test_embedder_failure_does_not_abort_ingest(self, temp_workspace, monkeypatch):
        monkeypatch.setitem(sys.modules, "torch", MagicMock())
        monkeypatch.setitem(sys.modules, "olmoearth_pretrain", MagicMock())
        raise_exc = RuntimeError("torch is broken right now")

        class FailingEmbedder:
            space_id = "image.olmoearth-nano-v12.v1"
            model_id = "olmoearth-nano-v1.2"

            def __init__(self, _p):
                pass

            def embed_images(self, images):
                raise raise_exc

            def embed_texts(self, texts):
                return None

        monkeypatch.setattr(
            "geomemory.embeddings.olmoearth_vision.OlmoEarthVisionEmbedder",
            FailingEmbedder,
        )
        with patch.object(temp_workspace, "_parse_spatial_source") as mock_parse:
            mock_parse.return_value = ([], {"scene": {}, "tiles": []})
            col = temp_workspace.create_collection("rs")
            src = temp_workspace.path / "dummy.tif"
            src.write_bytes(b"tiff")
            try:
                temp_workspace.update_settings(vision_path="/models/x")
                job = temp_workspace.ingest(src, col.id)
                assert job.state == "completed"
            finally:
                temp_workspace.update_settings(vision_path=None)


class TestImageIndexSpaceId:
    def test_space_id_matches_embedder(self):
        from geomemory.embeddings.olmoearth_vision import OlmoEarthVisionEmbedder
        from geomemory.index.image_index import ImageIndex

        assert ImageIndex.space_id == OlmoEarthVisionEmbedder.space_id


class TestVisionPathSpikeScripts:
    def test_export_script_exists(self):
        root = Path(__file__).resolve().parents[4]
        script = root / "scripts" / "export_olmoearth_onnx.py"
        assert script.exists(), "export_olmoearth_onnx.py must exist per Track B"

    def test_benchmark_script_exists(self):
        root = Path(__file__).resolve().parents[4]
        script = root / "scripts" / "benchmark_olmoearth_onnx.py"
        assert script.exists(), "benchmark_olmoearth_onnx.py must exist per Track B"
