"""Integration tests for spatial and temporal query support."""

from __future__ import annotations

import hashlib

import pytest

from geomemory.core.models import (
    Asset,
    AssetRevision,
    Observation,
    SearchHit,
    Segment,
    SpatialFilter,
    TemporalFilter,
)
from geomemory.retrieval.spatial_filter import apply_spatial_filter
from geomemory.retrieval.temporal_filter import apply_temporal_filter
from geomemory.rs.persist import persist_scene, persist_vector_layer
from geomemory.storage.repositories.asset_repo import (
    AssetRepository,
    AssetRevisionRepository,
)
from geomemory.storage.repositories.segment_repo import SegmentRepository
from geomemory.storage.repositories.spatial_repo import (
    ObservationRepository,
    RasterSceneRepository,
    RasterTileRepository,
    SpatialRepository,
    VectorLayerRepository,
)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _make_revision(ws) -> str:
    asset = Asset(collection_id=ws.create_collection("docs").id, kind="raster")
    AssetRepository(ws.conn).insert(asset)
    revision = AssetRevision(asset_id=asset.id, hash=_sha("x"), mime_type="image/tiff")
    AssetRevisionRepository(ws.conn).insert(revision)
    ws.conn.execute(
        "UPDATE asset SET current_revision_id = ? WHERE id = ?", (revision.id, asset.id)
    )
    ws.conn.commit()
    return revision.id


def _seg(ws, revision_id, text, spatial):
    segment = Segment(revision_id=revision_id, text=text, metadata={"spatial": spatial})
    SegmentRepository(ws.conn).insert(segment)
    return segment.id


S2_IN = {"bbox": [51.0, 35.0, 52.0, 36.0], "acquired_at": "2024-06-01", "sensor": "Sentinel-2"}
S2_OUT = {"bbox": [60.0, 60.0, 61.0, 61.0], "acquired_at": "2025-01-01", "sensor": "Landsat-8"}


class TestFilterModules:
    def _hit(self, sid, spatial):
        return SearchHit(id=sid, text="Sentinel-2", metadata={"spatial": spatial})

    def test_spatial_intersects(self):
        hits = [self._hit("a", S2_IN), self._hit("b", S2_OUT)]
        filtered = apply_spatial_filter(hits, SpatialFilter(bbox=(51.5, 35.5, 51.8, 35.8)))
        assert [h.id for h in filtered] == ["a"]

    def test_spatial_contains(self):
        hits = [self._hit("a", S2_IN), self._hit("b", S2_OUT)]
        filtered = apply_spatial_filter(hits, SpatialFilter(op="contains", bbox=(51.0, 35.0, 52.0, 36.0)))
        assert "a" in [h.id for h in filtered]

    def test_spatial_filter_excludes_hits_without_bbox(self):
        hits = [SearchHit(id="no-geo", text="plain")]
        assert apply_spatial_filter(hits, SpatialFilter(bbox=(0.0, 0.0, 1.0, 1.0))) == []

    def test_temporal_in_range(self):
        hits = [self._hit("a", S2_IN), self._hit("b", S2_OUT)]
        filtered = apply_temporal_filter(
            hits, TemporalFilter(field="acquired_at", from_="2024-01-01", to="2024-12-31")
        )
        assert [h.id for h in filtered] == ["a"]


class TestSpatialPersistence:
    def test_persist_scene_and_query(self, temp_workspace):
        ws = temp_workspace
        revision_id = _make_revision(ws)
        payload = {
            "scene": {
                "crs": "EPSG:4326",
                "bbox": [51.0, 35.0, 52.0, 36.0],
                "transform": [0.01, 0.0, 51.0, 0.0, -0.01, 36.0],
                "bands": [{"index": 1, "name": "Red"}, {"index": 2, "name": "NIR"}],
                "sensor": "Sentinel-2",
                "acquired_at": "2024-06-01",
                "width": 100,
                "height": 100,
            },
            "tiles": [
                {
                    "window": {"x": 0, "y": 0, "width": 100, "height": 100},
                    "transform": [0.01, 0.0, 51.0, 0.0, -0.01, 36.0],
                }
            ],
        }
        scene = persist_scene(ws.conn, revision_id, payload["scene"], tiles=payload["tiles"])
        scenes = RasterSceneRepository(ws.conn).get_by_revision(revision_id)
        assert len(scenes) == 1
        assert scenes[0].sensor == "Sentinel-2"

        tiles = RasterTileRepository(ws.conn).get_by_scene(scene.id)
        assert len(tiles) == 1
        assert tiles[0].window["width"] == 100

        ids = SpatialRepository(ws.conn).intersects((51.5, 35.5, 51.8, 35.8))
        assert scene.id in ids

    def test_persist_vector_layer(self, temp_workspace):
        ws = temp_workspace
        revision_id = _make_revision(ws)
        layer = persist_vector_layer(
            ws.conn,
            revision_id,
            {
                "geometry_type": "Polygon",
                "crs": "EPSG:4326",
                "bbox": [10.0, 20.0, 11.0, 21.0],
                "feature_count": 4,
                "properties": ["landcover"],
            },
        )
        layers = VectorLayerRepository(ws.conn).get_by_revision(revision_id)
        assert len(layers) == 1
        assert layers[0].feature_count == 4
        assert layers[0].metadata["bbox"] == [10.0, 20.0, 11.0, 21.0]
        assert layer.id in SpatialRepository(ws.conn).intersects((10.5, 20.5, 10.8, 20.8))

    def test_observation_repository(self, temp_workspace):
        ws = temp_workspace
        observation = Observation(
            subject_id="scn_1", subject_type="raster_scene", metric="ndvi_mean", value=0.42
        )
        ObservationRepository(ws.conn).insert(observation)
        found = ObservationRepository(ws.conn).get_by_subject("scn_1")
        assert len(found) == 1
        assert found[0].value == pytest.approx(0.42)



class TestWorkspaceSearch:
    def test_search_with_spatial_filter(self, temp_workspace):
        ws = temp_workspace
        revision_id = _make_revision(ws)
        _seg(ws, revision_id, "Sentinel-2 flood scene rice crop", S2_IN)
        _seg(ws, revision_id, "completely different content vocabulary xylophone", S2_OUT)

        result = ws.search("Sentinel", spatial=SpatialFilter(bbox=(51.5, 35.5, 51.8, 35.8)))
        assert result.total_hits == 1
        assert "Sentinel-2 flood scene" in result.hits[0].text

        outside = ws.search("Sentinel", spatial=SpatialFilter(bbox=(60.5, 60.5, 60.8, 60.8)))
        assert outside.total_hits == 1
        assert "completely different" in outside.hits[0].text

    def test_search_with_temporal_filter(self, temp_workspace):
        ws = temp_workspace
        revision_id = _make_revision(ws)
        _seg(ws, revision_id, "Sentinel-2 flood scene rice crop", S2_IN)
        _seg(ws, revision_id, "Sentinel-2 later scene watermark", S2_OUT)

        result = ws.search(
            "Sentinel",
            temporal=TemporalFilter(field="acquired_at", from_="2024-01-01", to="2024-12-31"),
        )
        assert [h.text for h in result.hits] == ["Sentinel-2 flood scene rice crop"]

    def test_search_with_sensor_filter(self, temp_workspace):
        ws = temp_workspace
        revision_id = _make_revision(ws)
        _seg(ws, revision_id, "Sentinel-2 flood scene rice crop", S2_IN)
        _seg(ws, revision_id, "Sentinel-2 later scene watermark", S2_OUT)

        result = ws.search("Sentinel", sensor=["Landsat-8"])
        assert result.total_hits == 1
        assert "later scene watermark" in result.hits[0].text

    def test_inspect_includes_scene(self, temp_workspace):
        ws = temp_workspace
        revision_id = _make_revision(ws)
        persist_scene(
            ws.conn,
            revision_id,
            {
                "crs": "EPSG:4326",
                "bbox": [51.0, 35.0, 52.0, 36.0],
                "sensor": "Sentinel-2",
                "bands": [],
            },
        )
        assets = AssetRepository(ws.conn).list_all()
        detail = ws.inspect(assets[0].id)
        assert len(detail.scenes) == 1
        assert detail.scenes[0].sensor == "Sentinel-2"

