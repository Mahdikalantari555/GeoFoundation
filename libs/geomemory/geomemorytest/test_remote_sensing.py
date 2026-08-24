"""Domain-specific tests for remote sensing content and spatiotemporal queries."""
from __future__ import annotations

import hashlib

import pytest

from geomemory.core.models import (
    Asset,
    AssetRevision,
    Collection,
    Observation,
    SearchHit,
    SearchResult,
    Segment,
    SpatialFilter,
    TemporalFilter,
)
from geomemory.retrieval.spatial_filter import apply_spatial_filter
from geomemory.retrieval.temporal_filter import apply_temporal_filter
from geomemory.retrieval.deduplicator import deduplicate
from geomemory.rs.persist import persist_scene, persist_vector_layer
from geomemory.storage.repositories.asset_repo import AssetRepository


# ===========================================================================
# RS-specific spatial indexing and filtering
# ===========================================================================

class TestRSSpatialFiltering:
    """Bounding-box and distance filtering as used for Sentinel/Landsat scenes."""

    def _scene_hit(self, bbox, sensor="Sentinel-2", acquired_at="2024-06-15T10:00:00"):
        return SearchHit(
            id="scene1",
            score=1.0,
            metadata={
                "spatial": {
                    "bbox": list(bbox),
                    "sensor": sensor,
                    "crs": "EPSG:4326",
                    "acquired_at": acquired_at,
                }
            },
        )

    def test_sentinel2_scene_intersects_query(self):
        query = SpatialFilter(bbox=(51.0, 35.0, 52.0, 36.0), op="intersects")
        hit = self._scene_hit((51.5, 35.5, 51.8, 35.8), sensor="Sentinel-2")
        assert apply_spatial_filter([hit], query) == [hit]

    def test_landsat8_scene_within_query(self):
        query = SpatialFilter(bbox=(50.0, 34.0, 53.0, 37.0), op="within")
        hit = self._scene_hit((51.0, 35.0, 52.0, 36.0), sensor="Landsat-8")
        assert apply_spatial_filter([hit], query) == [hit]

    def test_scene_outside_bbox_excluded(self):
        query = SpatialFilter(bbox=(51.0, 35.0, 52.0, 36.0), op="intersects")
        hit = self._scene_hit((80.0, 40.0, 81.0, 41.0), sensor="Sentinel-1")
        assert apply_spatial_filter([hit], query) == []

    def test_distance_lte_50km(self):
        """Two scenes ~30 km apart should match distance_lte 50km."""
        query = SpatialFilter(
            bbox=(51.0, 35.0, 51.01, 35.01),
            op="distance_lte",
            distance_m=50000,
        )
        hit = self._scene_hit((51.2, 35.2, 51.21, 35.21))
        assert apply_spatial_filter([hit], query) == [hit]

    def test_distance_lte_1km_excludes_far_scene(self):
        query = SpatialFilter(
            bbox=(51.0, 35.0, 51.01, 35.01),
            op="distance_lte",
            distance_m=1000,
        )
        hit = self._scene_hit((51.5, 35.5, 51.51, 35.51))
        assert apply_spatial_filter([hit], query) == []

    def test_temporal_filter_scene_date_range(self):
        filt = TemporalFilter(from_="2024-06-01", to="2024-06-30", field="acquired_at")
        hit_in = self._scene_hit((51.0, 35.0, 52.0, 36.0), acquired_at="2024-06-15T10:00:00")
        hit_out = self._scene_hit((51.0, 35.0, 52.0, 36.0), acquired_at="2024-01-01T00:00:00")
        result = apply_temporal_filter([hit_in, hit_out], filt)
        assert result == [hit_in]

    def test_temporal_filter_night_vs_day_scenes(self):
        """Both day and night acquisitions within June 2024 should match."""
        filt = TemporalFilter(from_="2024-06-01", to="2024-06-30", field="acquired_at")
        day = self._scene_hit((51.0, 35.0, 52.0, 36.0), acquired_at="2024-06-15T10:00:00")
        night = self._scene_hit((51.0, 35.0, 52.0, 36.0), acquired_at="2024-06-15T22:30:00")
        result = apply_temporal_filter([day, night], filt)
        assert len(result) == 2


# ===========================================================================
# Persisting scenes and vector layers: dirty geometries and empty metadata
# ===========================================================================

class TestRSPersistDirtyGeometries:
    def test_persist_scene_minimal_metadata(self, tmp_db):
        asset_repo = AssetRepository(tmp_db)
        # Create a workspace and collection first.
        tmp_db.execute("INSERT INTO workspace (id, name) VALUES (?, ?)", ("ws_rs", "rs-test"))
        col = Collection(workspace_id="ws_rs", name="rs-test")
        tmp_db.execute("INSERT INTO collection (id, workspace_id, name) VALUES (?, ?, ?)",
                        (col.id, col.workspace_id, col.name))
        asset = Asset(collection_id=col.id, kind="raster")
        asset_repo.insert(asset)
        rev = AssetRevision(asset_id=asset.id, hash="0" * 64, mime_type="image/tiff")
        from geomemory.storage.repositories.asset_repo import AssetRevisionRepository
        AssetRevisionRepository(tmp_db).insert(rev)

        scene_id = persist_scene(tmp_db, rev.id, {
            "bbox": [51.0, 35.0, 52.0, 36.0],
            "sensor": "Sentinel-2",
            "bands": [],
        })
        assert scene_id is not None

    def test_persist_scene_missing_crs_uses_default(self, tmp_db):
        """persist_scene without explicit CRS should default to EPSG:4326."""
        asset_repo = AssetRepository(tmp_db)
        tmp_db.execute("INSERT INTO workspace (id, name) VALUES (?, ?)", ("ws_rs2", "rs-test2"))
        col = Collection(workspace_id="ws_rs2", name="rs-test2")
        tmp_db.execute("INSERT INTO collection (id, workspace_id, name) VALUES (?, ?, ?)",
                        (col.id, col.workspace_id, col.name))
        asset = Asset(collection_id=col.id, kind="raster")
        asset_repo.insert(asset)
        rev = AssetRevision(asset_id=asset.id, hash="0" * 64, mime_type="image/tiff")
        from geomemory.storage.repositories.asset_repo import AssetRevisionRepository
        AssetRevisionRepository(tmp_db).insert(rev)

        scene = persist_scene(tmp_db, rev.id, {"bbox": [0, 0, 1, 1]})
        assert scene is not None
        assert scene.crs == "EPSG:4326"

    def test_persist_vector_layer_empty_properties(self, tmp_db):
        asset_repo = AssetRepository(tmp_db)
        tmp_db.execute("INSERT INTO workspace (id, name) VALUES (?, ?)", ("ws_vec", "vec-test"))
        col = Collection(workspace_id="ws_vec", name="vec-test")
        tmp_db.execute("INSERT INTO collection (id, workspace_id, name) VALUES (?, ?, ?)",
                        (col.id, col.workspace_id, col.name))
        asset = Asset(collection_id=col.id, kind="vector")
        asset_repo.insert(asset)
        rev = AssetRevision(asset_id=asset.id, hash="0" * 64, mime_type="application/geo+json")
        from geomemory.storage.repositories.asset_repo import AssetRevisionRepository
        AssetRevisionRepository(tmp_db).insert(rev)

        layer = persist_vector_layer(tmp_db, rev.id, {
            "geometry": {"type": "Point", "coordinates": [51.0, 35.0]},
            "properties": {},
        })
        assert layer is not None

    def test_persist_vector_layer_without_geometry_key(self, tmp_db):
        """persist_vector_layer with no geometry key should still create a record."""
        asset_repo = AssetRepository(tmp_db)
        tmp_db.execute("INSERT INTO workspace (id, name) VALUES (?, ?)", ("ws_vec2", "vec-test2"))
        col = Collection(workspace_id="ws_vec2", name="vec-test2")
        tmp_db.execute("INSERT INTO collection (id, workspace_id, name) VALUES (?, ?, ?)",
                        (col.id, col.workspace_id, col.name))
        asset = Asset(collection_id=col.id, kind="vector")
        asset_repo.insert(asset)
        rev = AssetRevision(asset_id=asset.id, hash="0" * 64, mime_type="application/geo+json")
        from geomemory.storage.repositories.asset_repo import AssetRevisionRepository
        AssetRevisionRepository(tmp_db).insert(rev)

        layer = persist_vector_layer(tmp_db, rev.id, {"properties": {}})
        assert layer is not None
        assert layer.geometry_type == "GeometryCollection"


# ===========================================================================
# RS-domain search: realistic queries over ingested content
# ===========================================================================

class TestRSSearchScenarios:
    """Simulate RS-domain search with manually constructed segments and hits."""

    def test_ndvi_segment_ranking(self):
        """NDVI-heavy text with a higher raw score should win in linear fusion."""
        ndvi_seg = SearchHit(
            id="seg1",
            score=0.95,
            metadata={"text": "NDVI vegetation health index computation", "segment_type": "paragraph"},
        )
        generic = SearchHit(id="seg2", score=0.3, metadata={"text": "general remote sensing notes"})
        hits = [ndvi_seg, generic]
        # With linear fusion and equal weights, the higher raw score wins.
        from geomemory.retrieval.fusion import linear_fuse
        fused = linear_fuse([hits], top_n=2)
        assert fused[0].id == "seg1"

    def test_sar_vs_optical_sensor_filtering(self):
        hits = [
            SearchHit(id="s1", score=1.0, metadata={"spatial": {"sensor": "Sentinel-1", "bbox": [0, 0, 1, 1]}}),
            SearchHit(id="s2", score=0.9, metadata={"spatial": {"sensor": "Sentinel-2", "bbox": [0, 0, 1, 1]}}),
        ]
        filt = SpatialFilter(bbox=(0, 0, 1, 1))
        filtered = apply_spatial_filter(hits, filt)
        assert len(filtered) == 2

    def test_multispectral_band_metadata_preserved(self):
        bands = ["B02", "B03", "B04", "B08"]
        hit = SearchHit(
            id="seg1",
            score=1.0,
            metadata={"spatial": {"sensor": "Sentinel-2", "bands": bands, "bbox": [0, 0, 1, 1]}},
        )
        assert hit.metadata["spatial"]["bands"] == bands

    def test_crop_stress_time_series_query(self):
        """A time-series search for crop stress should match June scenes."""
        scenes = [
            SearchHit(
                id=f"scene{i}",
                score=1.0,
                metadata={"spatial": {"acquired_at": f"2024-06-{day:02d}T10:00:00", "bbox": [0, 0, 1, 1]}},
            )
            for i, day in enumerate((10, 20, 25), start=1)
        ]
        filt = TemporalFilter(from_="2024-06-15", to="2024-06-30", field="acquired_at")
        result = apply_temporal_filter(scenes, filt)
        assert len(result) == 2
        assert {h.id for h in result} == {"scene2", "scene3"}

    def test_ambiguous_query_deduplication(self):
        """Ambiguous queries should not return duplicate segments."""
        hits = [
            SearchHit(id="seg1", score=1.0, metadata={"text": "NDVI crop stress", "revision_id": "r1"}),
            SearchHit(id="seg1", score=0.9, metadata={"text": "NDVI crop stress", "revision_id": "r1"}),
            SearchHit(id="seg2", score=0.8, metadata={"text": "NDVI crop stress", "revision_id": "r2"}),
        ]
        result = deduplicate(hits)
        assert len(result) == 2
