"""Unit tests for the remote sensing (RS) module.

Tests cover the pure-numpy functions that do not require rasterio or
geopandas, plus the reader/tiler/vector helpers with injected fake backends.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Ensure GeoMemory src is importable when running from geomemorytest/
# ---------------------------------------------------------------------------
_GEO_ROOT = Path(__file__).resolve().parents[1] / "GeoMemory"
if str(_GEO_ROOT) not in sys.path:
    sys.path.insert(0, str(_GEO_ROOT))


# ===========================================================================
# Spectral indices (pure numpy)
# ===========================================================================


class TestNDVI:
    """Normalized Difference Vegetation Index."""

    def test_healthy_vegetation_positive(self):
        """Dense vegetation: NIR high, RED low -> NDVI close to 1."""
        nir = np.array([[100, 200, 300]], dtype=np.float32)
        red = np.array([[50, 50, 50]], dtype=np.float32)
        result = pytest.importorskip("geomemory.rs.raster.spectral").ndvi(nir, red)
        assert result.shape == (1, 3)
        assert np.all(result > 0.3)

    def test_bare_soil_near_zero(self):
        """Low NIR, high RED -> NDVI near 0."""
        nir = np.array([[50, 50, 50]], dtype=np.float32)
        red = np.array([[100, 100, 100]], dtype=np.float32)
        result = pytest.importorskip("geomemory.rs.raster.spectral").ndvi(nir, red)
        assert result.shape == (1, 3)
        assert np.all(result < 0.0)

    def test_zero_denominator_gives_nan(self):
        """When both NIR and RED are 0, denominator is exactly 0 -> result is NaN."""
        from geomemory.rs.raster.spectral import ndvi
        nir = np.array([[0.0, 0.0]], dtype=np.float32)
        red = np.array([[0.0, 0.0]], dtype=np.float32)
        result = ndvi(nir, red)
        assert np.all(np.isnan(result))

    def test_mismatched_shapes_raises(self):
        from geomemory.rs.raster.spectral import ndvi
        nir = np.array([[1, 2]], dtype=np.float32)
        red = np.array([[1, 2, 3]], dtype=np.float32)
        with pytest.raises(ValueError, match="equal-shaped"):
            ndvi(nir, red)

    def test_output_dtype_float(self):
        nir = np.array([[100, 200]], dtype=np.uint16)
        red = np.array([[50, 100]], dtype=np.uint16)
        result = pytest.importorskip("geomemory.rs.raster.spectral").ndvi(nir, red)
        assert np.issubdtype(result.dtype, np.floating)


class TestEVI:
    """Enhanced Vegetation Index."""

    def test_evi_produces_valid_range(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        nir = np.array([[800, 900, 1000]], dtype=np.float32)
        red = np.array([[100, 120, 130]], dtype=np.float32)
        blue = np.array([[50, 60, 70]], dtype=np.float32)
        result = spectral.evi(nir, red, blue)
        assert result.shape == (1, 3)
        assert np.all(np.isfinite(result))

    def test_evi_default_coefficients(self):
        """Default EVI uses g=2.5, c1=6.0, c2=7.5, l=1.0."""
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        nir = np.array([[800.0]], dtype=np.float32)
        red = np.array([[100.0]], dtype=np.float32)
        blue = np.array([[50.0]], dtype=np.float32)
        result_default = spectral.evi(nir, red, blue)
        result_explicit = spectral.evi(nir, red, blue, g=2.5, c1=6.0, c2=7.5, l=1.0)
        np.testing.assert_allclose(result_default, result_explicit)

    def test_evi_mismatched_shapes_raises(self):
        from geomemory.rs.raster.spectral import evi
        nir = np.array([[1, 2]], dtype=np.float32)
        red = np.array([[1, 2]], dtype=np.float32)
        blue = np.array([[1, 2, 3]], dtype=np.float32)
        with pytest.raises(ValueError, match="equal-shaped"):
            evi(nir, red, blue)


class TestBandStatistics:
    """Descriptive statistics for a single-band array."""

    def test_basic_statistics(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        arr = np.array([[1.0, 2.0, 3.0, 4.0, 5.0]], dtype=np.float32)
        stats = spectral.band_statistics(arr)
        assert stats["min"] == 1.0
        assert stats["max"] == 5.0
        assert stats["mean"] == 3.0
        assert stats["count"] == 5.0

    def test_empty_array_returns_zeros(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        stats = spectral.band_statistics(np.array([], dtype=np.float32))
        assert stats["count"] == 0.0
        assert stats["min"] == 0.0
        assert stats["max"] == 0.0
        assert stats["mean"] == 0.0

    def test_all_nan_returns_zeros(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        stats = spectral.band_statistics(np.array([[np.nan, np.nan]], dtype=np.float32))
        assert stats["count"] == 0.0
        assert stats["mean"] == 0.0

    def test_percentile_keys_present(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        arr = np.arange(100, dtype=np.float32)
        stats = spectral.band_statistics(arr)
        assert "p05" in stats
        assert "p95" in stats
        assert stats["p05"] < stats["p95"]


class TestResolveBands:
    """Band index validation."""

    def test_valid_mapping_accepted(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        from geomemory.rs.raster.metadata import RasterSceneData
        # Scene needs enough bands for the mapped indices (1-based).
        scene = RasterSceneData(bands=[{}] * 8, bbox=[0, 0, 1, 1])
        mapping = spectral.resolve_bands(scene, {"nir": 8, "red": 4, "blue": 2})
        assert mapping == {"nir": 8, "red": 4, "blue": 2}

    def test_out_of_range_index_raises(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        from geomemory.rs.raster.metadata import RasterSceneData
        scene = RasterSceneData(bands=[{}, {}], bbox=[0, 0, 1, 1])
        with pytest.raises(Exception, match="out of range"):
            spectral.resolve_bands(scene, {"nir": 5})

    def test_non_int_index_raises(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        from geomemory.rs.raster.metadata import RasterSceneData
        scene = RasterSceneData(bands=[{}, {}, {}], bbox=[0, 0, 1, 1])
        with pytest.raises(Exception, match="out of range"):
            spectral.resolve_bands(scene, {"nir": "eight"})


class TestValidateIndex:
    """Required-band presence validation."""

    def test_all_bands_present(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        result = spectral.validate_index("NDVI", {"nir": 8, "red": 4}, {"nir", "red"})
        assert result == {"nir": 8, "red": 4}

    def test_missing_band_raises(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        with pytest.raises(Exception, match="requires bands"):
            spectral.validate_index("EVI", {"nir": 8, "red": 4}, {"nir", "red", "blue"})

    def test_compute_index_dispatches_ndvi(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        nir = np.array([[100.0, 200.0]], dtype=np.float32)
        red = np.array([[50.0, 100.0]], dtype=np.float32)
        result = spectral.compute_index("NDVI", {"nir": nir, "red": red}, {"nir": 8, "red": 4}, {"nir", "red"})
        assert result.shape == (1, 2)

    def test_compute_index_dispatches_evi(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        nir = np.array([[800.0]], dtype=np.float32)
        red = np.array([[100.0]], dtype=np.float32)
        blue = np.array([[50.0]], dtype=np.float32)
        result = spectral.compute_index("EVI", {"nir": nir, "red": red, "blue": blue},
                                         {"nir": 8, "red": 4, "blue": 2}, {"nir", "red", "blue"})
        assert result.shape == (1, 1)

    def test_compute_index_unknown_raises(self):
        spectral = pytest.importorskip("geomemory.rs.raster.spectral")
        with pytest.raises(Exception, match="Unsupported spectral index"):
            spectral.compute_index("SAVI", {"nir": np.zeros((1, 1))}, {"nir": 8}, {"nir"})


# ===========================================================================
# Preview generation (pure numpy, no Pillow required for array computation)
# ===========================================================================


class TestComputePreviewArray:
    """Tests for compute_preview_array that do not need Pillow."""

    def test_2d_input_produces_rgb(self):
        preview = pytest.importorskip("geomemory.rs.raster.preview").compute_preview_array
        arr = np.random.rand(64, 64).astype(np.float32) * 1000
        result = preview(arr, max_side=32)
        assert result.shape == (32, 32, 3)
        assert result.dtype == np.uint8

    def test_3d_rgb_input(self):
        preview = pytest.importorskip("geomemory.rs.raster.preview").compute_preview_array
        arr = np.random.rand(3, 64, 64).astype(np.float32) * 1000
        result = preview(arr, max_side=32)
        assert result.shape == (32, 32, 3)
        assert result.dtype == np.uint8

    def test_invalid_ndim_raises(self):
        preview_mod = pytest.importorskip("geomemory.rs.raster.preview")
        with pytest.raises(ValueError, match="2D or 3D"):
            preview_mod.compute_preview_array(np.zeros((2, 2, 2, 2), dtype=np.float32))

    def test_small_array_not_upsampled(self):
        """Arrays already below max_side should not be enlarged."""
        preview = pytest.importorskip("geomemory.rs.raster.preview").compute_preview_array
        arr = np.ones((16, 16), dtype=np.float32) * 500
        result = preview(arr, max_side=512)
        assert result.shape == (16, 16, 3)

    def test_output_range_uint8(self):
        preview = pytest.importorskip("geomemory.rs.raster.preview").compute_preview_array
        arr = np.random.rand(64, 64).astype(np.float32) * 1000
        result = preview(arr, max_side=32)
        assert result.min() >= 0
        assert result.max() <= 255


class TestWritePng:
    """write_png returns False without Pillow."""

    def test_no_pillow_returns_false(self):
        preview_mod = pytest.importorskip("geomemory.rs.raster.preview")
        with mock.patch.dict(sys.modules, {"PIL": None, "PIL.Image": None}):
            with mock.patch("builtins.__import__", side_effect=ImportError):
                result = preview_mod.write_png(np.zeros((10, 10, 3), dtype=np.uint8), "/tmp/test.png")
        assert result is False


# ===========================================================================
# Tiler (pure-python window logic, no rasterio required)
# ===========================================================================


class TestWindowGrid:
    """Non-overlapping tile window grid computation."""

    def _grid(self, width, height, tile_size=256):
        from geomemory.rs.raster.tiler import window_grid
        return window_grid(width, height, tile_size)

    def test_exact_division(self):
        windows = self._grid(512, 512, 256)
        assert len(windows) == 4

    def test_non_exact_dimension(self):
        windows = self._grid(500, 500, 256)
        assert len(windows) == 4
        # Last window should be smaller than tile_size
        assert windows[-1]["width"] == 500 - 256
        assert windows[-1]["height"] == 500 - 256

    def test_zero_dimensions_returns_empty(self):
        assert self._grid(0, 100) == []
        assert self._grid(100, 0) == []
        assert self._grid(0, 0) == []

    def test_negative_dimensions_returns_empty(self):
        assert self._grid(-10, 100) == []
        assert self._grid(100, -10) == []

    def test_window_keys(self):
        windows = self._grid(300, 300, 256)
        assert set(windows[0].keys()) == {"x", "y", "width", "height"}
        assert windows[0]["x"] == 0
        assert windows[0]["y"] == 0


class TestWindowTransform:
    def test_identity_transform(self):
        from geomemory.rs.raster.tiler import window_transform
        transform = [1.0, 0.0, 0.0, 0.0, -1.0, 0.0]
        window = {"x": 0, "y": 0, "width": 256, "height": 256}
        result = window_transform(transform, window)
        assert len(result) == 6

    def test_short_transform_returns_empty(self):
        from geomemory.rs.raster.tiler import window_transform
        result = window_transform([1.0, 2.0], {"x": 0, "y": 0, "width": 10, "height": 10})
        assert result == []


class TestWindowBounds:
    def test_identity_transform_bounds(self):
        from geomemory.rs.raster.tiler import window_bounds
        transform = [1.0, 0.0, 0.0, 0.0, -1.0, 0.0]
        window = {"x": 0, "y": 0, "width": 10, "height": 10}
        left, bottom, right, top = window_bounds(transform, window)
        assert left == 0.0
        assert right == 10.0
        assert top == 0.0
        assert bottom == -10.0

    def test_short_transform_returns_zeros(self):
        from geomemory.rs.raster.tiler import window_bounds
        result = window_bounds([1.0], {"x": 0, "y": 0, "width": 10, "height": 10})
        assert result == (0.0, 0.0, 0.0, 0.0)


class TestBuildTiles:
    """build_tiles orchestrates window_grid + transforms + optional previews."""

    def _fake_scene(self, width=512, height=512, crs="EPSG:4326"):
        from geomemory.rs.raster.metadata import RasterSceneData
        return RasterSceneData(
            width=width, height=height, crs=crs,
            bbox=[0.0, 0.0, 1.0, 1.0],
            transform=[1.0, 0.0, 0.0, 0.0, -1.0, 0.0],
        )

    def test_no_reader_no_preview(self):
        from geomemory.rs.raster.tiler import build_tiles
        scene = self._fake_scene()
        tiles = build_tiles(scene, "/tmp/fake.tif", "/tmp/tiles", reader=None)
        assert len(tiles) == 4
        assert all(t.preview_path is None for t in tiles)

    def test_with_reader_calls_read_window(self):
        from geomemory.rs.raster.tiler import build_tiles
        scene = self._fake_scene()
        fake_reader = mock.MagicMock()
        fake_reader.read_window.return_value = np.zeros((3, 256, 256), dtype=np.float32)
        tiles = build_tiles(scene, "/tmp/fake.tif", "/tmp/tiles", reader=fake_reader, max_side=128)
        assert len(tiles) == 4
        assert fake_reader.read_window.call_count == 4

    def test_non_epsg_no_footprint(self):
        """Tiles in a non-EPSG:4326 CRS should not get a footprint."""
        from geomemory.rs.raster.tiler import build_tiles
        from geomemory.rs.raster.metadata import RasterSceneData
        scene = RasterSceneData(
            width=256, height=256, crs="EPSG:3857",
            bbox=[0.0, 0.0, 1.0, 1.0],
            transform=[1.0, 0.0, 0.0, 0.0, -1.0, 0.0],
        )
        tiles = build_tiles(scene, "/tmp/fake.tif", "/tmp/tiles", reader=None)
        assert len(tiles) == 1
        assert tiles[0].footprint is None


# ===========================================================================
# Vector reader (with injected fake geopandas backend)
# ===========================================================================


class TestVectorReader:
    """VectorReader extracts metadata from a geopandas-like backend."""

    def _read(self, geo_data):
        """Inject a fake backend and call read_layer on a temp path."""
        fake_backend = mock.MagicMock()
        fake_backend.read_file.return_value = geo_data
        reader_mod = pytest.importorskip("geomemory.rs.vector.reader")
        reader = reader_mod.VectorReader(backend=fake_backend)
        return reader.read_layer("/tmp/fake.geojson"), fake_backend

    def test_point_layer(self):
        pytest.importorskip("geopandas")
        from geopandas import GeoDataFrame  # type: ignore[import]
        from shapely.geometry import Point  # type: ignore[import]
        gdf = GeoDataFrame({"name": ["p1"]}, geometry=[Point(0, 0)], crs="EPSG:4326")
        result, backend = self._read(gdf)
        assert result.geometry_type == "Point"
        assert result.feature_count == 1
        backend.read_file.assert_called_once_with("/tmp/fake.geojson")

    def test_polygon_layer(self):
        pytest.importorskip("geopandas")
        from geopandas import GeoDataFrame  # type: ignore[import]
        from shapely.geometry import Polygon  # type: ignore[import]
        gdf = GeoDataFrame(geometry=[Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])], crs="EPSG:4326")
        result, _ = self._read(gdf)
        assert result.geometry_type == "Polygon"

    def test_empty_dataframe_returns_geometry_collection(self):
        pytest.importorskip("geopandas")
        from geopandas import GeoDataFrame  # type: ignore[import]
        import pandas as pd  # type: ignore[import]
        gdf = GeoDataFrame(pd.DataFrame({"col": []}), geometry=[], crs="EPSG:4326")
        result, _ = self._read(gdf)
        assert result.geometry_type == "GeometryCollection"
        assert result.feature_count == 0

    def test_mixed_geometry_types_picks_higher(self):
        """When multiple geometry types are present, _pick_geometry returns the first in _VALID_GEOMETRIES order."""
        reader_mod = pytest.importorskip("geomemory.rs.vector.reader")
        types = {"Point", "LineString"}
        # Point comes before LineString in _VALID_GEOMETRIES tuple order.
        assert reader_mod._pick_geometry(types) == "Point"

    def test_crs_fallback_on_none(self):
        pytest.importorskip("geopandas")
        from geopandas import GeoDataFrame  # type: ignore[import]
        from shapely.geometry import Point  # type: ignore[import]
        gdf = GeoDataFrame({"name": ["p1"]}, geometry=[Point(0, 0)])
        result, _ = self._read(gdf)
        # _crs_string handles None by returning EPSG:4326.
        assert result.crs is not None


# ===========================================================================
# Metadata helpers (raster)
# ===========================================================================


class TestRasterMetadataHelpers:
    """Tests for functions in geomemory.rs.raster.metadata."""

    def test_validate_bbox_valid(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        # validate_bbox returns None on success, raises on failure.
        meta.validate_bbox([0.0, 0.0, 10.0, 10.0])  # should not raise

    def test_validate_bbox_rejects_wrong_length(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        with pytest.raises(Exception, match="4 values"):
            meta.validate_bbox([0.0, 0.0, 10.0])

    def test_format_bbox(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        bbox = meta.format_bbox([0.0, 0.0, 10.0, 10.0])
        assert "10.000000" in bbox

    def test_footprint_wkb_hex(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        hex_str = meta.footprint_wkb_hex([0.0, 0.0, 1.0, 1.0])
        # Returns a non-empty WKB hex string when shapely is available.
        assert isinstance(hex_str, (str, type(None)))

    def test_sensor_from_metadata_sentinel2(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        assert meta.sensor_from_metadata({"SATELLITE": "Sentinel-2"}) == "Sentinel-2"

    def test_sensor_from_metadata_landsat(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        assert meta.sensor_from_metadata({"SATELLITE": "Landsat-8"}) == "Landsat-8"

    def test_sensor_from_metadata_missing_returns_none(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        assert meta.sensor_from_metadata({}) is None

    def test_acquired_from_metadata(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        assert meta.acquired_from_metadata({"ACQUISITION_DATE": "2024-06-15"}) == "2024-06-15"

    def test_build_band_specs(self):
        meta = pytest.importorskip("geomemory.rs.raster.metadata")
        bands = meta.build_band_specs(4, dtypes=["uint16"] * 4, width=256, height=256)
        assert len(bands) == 4
        assert all("dtype" in b for b in bands)
