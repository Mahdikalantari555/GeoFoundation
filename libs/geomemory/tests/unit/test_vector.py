"""Unit tests for the vector module reader and loader."""

from __future__ import annotations

import numpy as np
import pytest

from geomemory.core.exceptions import VectorBackendUnavailableError
from geomemory.core.models import SourceRef
from geomemory.ingest.loaders.geojson import GeoJsonLoader
from geomemory.rs.vector.reader import VectorReader, describe_layer


class FakeGeometry:
    def __init__(self, types, bounds):
        self._types = types
        self._bounds = np.asarray(bounds, dtype=float)

    @property
    def geom_type(self):
        return list(self._types)

    @property
    def total_bounds(self):
        return self._bounds


class FakeCrs:
    def to_epsg(self):
        return 4326


class FakeGdf:
    def __init__(self, *, types=("Polygon",), bounds=(0.0, 0.0, 10.0, 10.0), columns=("name", "geometry")):
        self.geometry = FakeGeometry(types, bounds)
        self.crs = FakeCrs()
        self.columns = list(columns)
        self._length = 3
        self.driver = "GeoJSON"

    def __len__(self):
        return self._length

    def head(self, limit):
        return self

    def to_dict(self, records):
        return [
            {"name": "field_a", "geometry": None},
            {"name": "field_b", "geometry": None},
        ]


class FakeBackend:
    def __init__(self, gdf_factory=None):
        self.gdf_factory = gdf_factory or (lambda path: FakeGdf())

    def read_file(self, path):
        return self.gdf_factory(path)


def test_read_layer_metadata():
    reader = VectorReader(backend=FakeBackend())
    layer = reader.read_layer("/tmp/layer.geojson")
    assert layer.geometry_type == "Polygon"
    assert layer.crs == "EPSG:4326"
    assert layer.bbox == [0.0, 0.0, 10.0, 10.0]
    assert layer.feature_count == 3
    assert layer.properties == ["name"]


def test_read_layer_empty_geometry():
    class EmptyGdf:
        def __init__(self):
            self.geometry = None
            self.crs = FakeCrs()
            self.driver = "unknown"

        def __len__(self):
            return 0

    reader = VectorReader(backend=FakeBackend(lambda path: EmptyGdf()))
    layer = reader.read_layer("/tmp/layer.geojson")
    assert layer.feature_count == 0
    assert layer.geometry_type == "GeometryCollection"
    assert layer.bbox == []


def test_describe_layer_includes_geometry_and_attributes():
    reader = VectorReader(backend=FakeBackend())
    layer = reader.read_layer("/tmp/layer.geojson")
    text = describe_layer(layer)
    assert "Polygon" in text
    assert "name" in text
    assert "3 feature(s)" in text


def test_reader_raises_when_geopandas_missing(monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "geopandas", None)
    reader = VectorReader()
    with pytest.raises(VectorBackendUnavailableError):
        reader.read_layer("/tmp/layer.geojson")


class TestGeoJsonLoader:
    def test_supports(self):
        loader = GeoJsonLoader(reader=VectorReader(backend=FakeBackend()))
        assert loader.supports(SourceRef(path="a.geojson"))
        assert loader.supports(SourceRef(path="b.gpkg"))
        assert not loader.supports(SourceRef(path="c.txt"))

    def test_load_yields_searchable_payload(self, tmp_path):
        loader = GeoJsonLoader(reader=VectorReader(backend=FakeBackend()))
        path = tmp_path / "layer.geojson"
        path.write_text("{}", encoding="utf-8")
        objs = list(loader.load(SourceRef(path=str(path))))
        assert len(objs) == 1
        obj = objs[0]
        assert obj.mime_type == "application/geo+json"
        assert obj.metadata["vector"]["layer"]["geometry_type"] == "Polygon"
        assert obj.metadata["vector"]["layer"]["crs"] == "EPSG:4326"
        assert "Polygon" in obj.text
