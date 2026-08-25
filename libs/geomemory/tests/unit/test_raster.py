"""Unit tests for the raster module (reader, preview, tiler, spectral)."""

from __future__ import annotations

import numpy as np
import pytest

from geomemory.core.exceptions import BandMappingError
from geomemory.ingest.loaders.geotiff import GeoTiffLoader
from geomemory.rs.raster.metadata import (
    RasterSceneData,
    bbox_from_bounds,
    build_band_specs,
    describe_scene,
    format_bbox,
    validate_bbox,
)
from geomemory.rs.raster.preview import compute_preview_array
from geomemory.rs.raster.reader import RasterReader
from geomemory.rs.raster.spectral import (
    band_statistics,
    evi,
    ndvi,
    resolve_bands,
    validate_index,
)
from geomemory.rs.raster.tiler import (
    window_bounds,
    window_grid,
    window_only_tiles,
    window_transform,
)


class FakeTransform:
    def __init__(self, a, b, c, d, e, f):
        self.a, self.b, self.c, self.d, self.e, self.f = a, b, c, d, e, f


class FakeDataset:
    def __init__(self, **kw):
        self.crs = kw.get("crs", "EPSG:4326")
        self.bounds = kw.get("bounds", (0.0, 0.0, 10.0, 10.0))
        self.transform = kw.get("transform", FakeTransform(1, 0, 0, 0, -1, 10))
        self.count = kw.get("count", 3)
        self.dtypes = kw.get("dtypes", ["uint16"] * 3)
        self.width = kw.get("width", 100)
        self.height = kw.get("height", 100)
        self.nodata = kw.get("nodata")
        self.descriptions = kw.get("descriptions", [])
        self._tags = kw.get("tags", {})
        self._array = kw.get("array")
        self._closed = False

    def tags(self):
        return self._tags

    def read(self, window=None):
        if self._array is not None:
            return self._array
        height = window["height"] if window else self.height
        width = window["width"] if window else self.width
        return np.zeros((self.count, height, width), dtype=np.float32)

    def close(self):
        self._closed = True


class FakeBackend:
    def __init__(self, dataset_factory=None):
        self.dataset_factory = dataset_factory or (lambda path: FakeDataset())
        self.opened: list[str] = []

    def open(self, path):
        self.opened.append(str(path))
        return self.dataset_factory(path)


def _scene() -> RasterSceneData:
    return RasterSceneData(
        crs="EPSG:4326",
        bbox=[51.0, 35.0, 52.0, 36.0],
        transform=[0.01, 0.0, 51.0, 0.0, -0.01, 36.0],
        bands=[
            {"index": 1, "name": "Blue"},
            {"index": 2, "name": "Red"},
            {"index": 3, "name": "NIR"},
        ],
        sensor="Sentinel-2",
        acquired_at="2024-06-01",
        width=100,
        height=100,
        resolution_m=10.0,
    )


class TestMetadata:
    def test_bbox_from_bounds(self):
        assert bbox_from_bounds(1.0, 2.0, 3.0, 4.0) == [1.0, 2.0, 3.0, 4.0]

    def test_build_band_specs(self):
        bands = build_band_specs(2, dtypes=["uint16", "float32"], width=10, height=10)
        assert bands[0]["index"] == 1
        assert bands[0]["dtype"] == "uint16"
        assert bands[1]["dtype"] == "float32"

    def test_validate_bbox_rejects_wrong_order(self):
        with pytest.raises(Exception):
            validate_bbox([10.0, 20.0, 5.0, 25.0])

    def test_describe_scene_includes_sensor_and_bands(self):
        text = describe_scene(_scene())
        assert "Sentinel-2" in text
        assert "NIR" in text
        assert "2024-06-01" in text

    def test_format_bbox(self):
        assert format_bbox([1.0, 2.0, 3.0, 4.0]) == "[1.000000, 2.000000, 3.000000, 4.000000]"


class TestReader:
    def test_read_scene_metadata(self):
        dataset = FakeDataset(
            crs="EPSG:4326",
            bounds=(0.0, 0.0, 10.0, 10.0),
            transform=FakeTransform(1, 0, 0, 0, -1, 10),
            count=3,
            dtypes=["int16", "int16", "int16"],
            tags={"SATELLITE": "Landsat-8", "ACQUISITION_DATE": "2024-03-15"},
            descriptions=["Blue", "Green", "Red"],
            width=10,
            height=10,
            nodata=-9999,
        )
        reader = RasterReader(backend=FakeBackend(lambda path: dataset))
        scene = reader.read_scene("/tmp/x.tif")
        assert scene.crs == "EPSG:4326"
        assert scene.bbox == [0.0, 0.0, 10.0, 10.0]
        assert scene.sensor == "Landsat-8"
        assert scene.acquired_at == "2024-03-15"
        assert scene.width == 10
        assert scene.dtype == "int16"
        assert scene.bands[0]["description"] == "Blue"
        assert dataset._closed is True

    def test_read_geographic_resolution_in_meters(self):
        dataset = FakeDataset(
            crs="EPSG:4326", transform=FakeTransform(0.01, 0, 0, 0, -0.01, 50), width=10, height=10
        )
        reader = RasterReader(backend=FakeBackend(lambda path: dataset))
        scene = reader.read_scene("/tmp/x.tif")
        assert scene.resolution_m == pytest.approx(0.01 * 111320.0, rel=1e-3)

    def test_read_window(self):
        reader = RasterReader(backend=FakeBackend(lambda path: FakeDataset(count=2, height=10, width=10)))
        arr = reader.read_window("/tmp/x.tif", {"x": 0, "y": 0, "width": 5, "height": 5})
        assert arr.shape == (2, 5, 5)

    def test_reader_raises_when_rasterio_missing(self):
        import sys

        sys.modules.pop("rasterio", None)
        reader = RasterReader()
        with pytest.raises(Exception):
            reader.read_scene("/tmp/x.tif")


class TestPreview:
    def test_2d_becomes_rgb_uint8(self):
        out = compute_preview_array(np.ones((4, 4), dtype=np.float64), max_side=8)
        assert out.shape == (4, 4, 3)
        assert out.dtype == np.uint8

    def test_3d_rgb_bands(self):
        arr = np.arange(3 * 10 * 10, dtype=np.float32).reshape(3, 10, 10)
        out = compute_preview_array(arr, max_side=10, rgb_bands=(3, 2, 1))
        assert out.shape == (10, 10, 3)

    def test_downsample(self):
        out = compute_preview_array(np.ones((100, 100), dtype=np.float32), max_side=50)
        assert out.shape[0] <= 50

    def test_preview_rejects_1d(self):
        with pytest.raises(ValueError):
            compute_preview_array(np.ones(10), max_side=5)



class TestTiler:
    def test_window_grid(self):
        windows = window_grid(100, 100, 50)
        assert len(windows) == 4
        assert windows[0] == {"x": 0, "y": 0, "width": 50, "height": 50}
        assert windows[-1]["width"] == 50

    def test_window_transform(self):
        transform = [0.01, 0.0, 51.0, 0.0, -0.01, 36.0]
        t = window_transform(transform, {"x": 10, "y": 20, "width": 10, "height": 10})
        assert t[0] == 0.01
        assert t[5] == pytest.approx(35.8)

    def test_window_bounds(self):
        transform = [0.01, 0.0, 51.0, 0.0, -0.01, 36.0]
        left, bottom, right, top = window_bounds(
            transform, {"x": 0, "y": 0, "width": 10, "height": 10}
        )
        assert left == 51.0
        assert top == 36.0
        assert right == 51.1
        assert bottom == 35.9

    def test_window_only_tiles_for_4326(self):
        tiles = window_only_tiles(_scene(), tile_size=50)
        assert len(tiles) == 4
        assert all(t.window["width"] > 0 for t in tiles)


class TestSpectral:
    def test_ndvi(self):
        out = ndvi(np.array([[150]]), np.array([[50]]))
        assert out[0, 0] == pytest.approx(0.5)

    def test_ndvi_zero_denominator_is_nan(self):
        out = ndvi(np.array([5.0]), np.array([-5.0]))
        assert np.isnan(out[0])

    def test_evi(self):
        out = evi(np.array([500.0]), np.array([100.0]), np.array([50.0]))
        assert not np.isnan(out[0])

    def test_ndvi_shape_mismatch(self):
        with pytest.raises(ValueError):
            ndvi(np.zeros(3), np.zeros(4))

    def test_band_statistics(self):
        stats = band_statistics(np.array([[1.0, 2.0], [3.0, 4.0]]))
        assert stats["mean"] == pytest.approx(2.5)
        assert stats["min"] == 1.0
        assert stats["max"] == 4.0

    def test_resolve_bands_in_range(self):
        scene = _scene()  # 3 bands
        assert resolve_bands(scene, {"nir": 3, "red": 2}) == {"nir": 3, "red": 2}

    def test_resolve_bands_out_of_range(self):
        with pytest.raises(BandMappingError):
            resolve_bands(_scene(), {"nir": 99})

    def test_validate_index_missing(self):
        with pytest.raises(BandMappingError):
            validate_index("NDVI", {"nir": 3}, {"nir", "red"})


class TestGeoTiffLoader:
    def test_supports(self):
        loader = GeoTiffLoader(reader=RasterReader(backend=FakeBackend()))
        from geomemory.core.models import SourceRef

        assert loader.supports(SourceRef(path="a.tif"))
        assert loader.supports(SourceRef(path="a.tiff"))
        assert not loader.supports(SourceRef(path="a.txt"))

    def test_load_yields_searchable_payload(self, tmp_path):
        backend = FakeBackend(
            lambda path: FakeDataset(
                tags={"SATELLITE": "Sentinel-2", "ACQUISITION_DATE": "2024-06-01"},
                count=3,
                width=100,
                height=100,
            )
        )
        loader = GeoTiffLoader(reader=RasterReader(backend=backend))
        path = tmp_path / "scene.tif"
        path.write_bytes(b"\x00")
        from geomemory.core.models import SourceRef

        objs = list(loader.load(SourceRef(path=str(path))))
        assert len(objs) == 1
        obj = objs[0]
        assert obj.mime_type == "image/tiff"
        assert "Sentinel-2" in obj.text
        assert obj.metadata["raster"]["scene"]["sensor"] == "Sentinel-2"
        assert obj.metadata["raster"]["tiles"] != []

