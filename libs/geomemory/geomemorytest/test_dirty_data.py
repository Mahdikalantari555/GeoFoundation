"""Dirty-data robustness tests for the GeoMemory core.

These tests exercise the system against malformed, missing, and otherwise
problematic inputs that tend to break thin wrappers around ML/search stacks.
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from geomemory.core.models import (
    Asset,
    AssetRevision,
    Collection,
    EmbeddingRecord,
    Job,
    QAResult,
    SearchFilters,
    SearchHit,
    Segment,
    SpatialFilter,
    TemporalFilter,
)
from geomemory.core.hashing import sha256_bytes
from geomemory.storage.object_store import ObjectStore
from geomemory.retrieval.deduplicator import deduplicate, enforce_diversity
from geomemory.retrieval.fusion import linear_fuse, rrf_fuse
from geomemory.retrieval.query_parser import QueryParser
from geomemory.retrieval.spatial_filter import apply_spatial_filter, spatial_ids
from geomemory.retrieval.temporal_filter import apply_temporal_filter, time_in_range
from geomemory.storage.repositories.asset_repo import AssetRepository
from geomemory.storage.repositories.segment_repo import SegmentRepository


# ===========================================================================
# Model validation: bad inputs must fail loudly, not silently corrupt
# ===========================================================================

class TestDirtyModelInputs:
    def test_invalid_bbox_tuple_length_raises(self):
        with pytest.raises(ValidationError):
            SpatialFilter(bbox=(0, 0, 1))

    def test_bbox_must_have_four_values(self):
        with pytest.raises(ValidationError):
            SpatialFilter(bbox=(0, 0, 1))

    def test_spatial_filter_requires_bbox_or_geometry_id(self):
        with pytest.raises(ValueError):
            SpatialFilter()

    def test_negative_distance_without_distance_m(self):
        with pytest.raises(ValueError):
            SpatialFilter(bbox=(0, 0, 1, 1), op="distance_lte")

    def test_temporal_filter_requires_from_or_to(self):
        with pytest.raises(ValueError):
            TemporalFilter()

    def test_temporal_from_after_to_raises(self):
        with pytest.raises(ValueError):
            TemporalFilter(from_="2025-01-01", to="2024-01-01")

    def test_bad_hex_hash_raises(self):
        with pytest.raises(ValidationError):
            AssetRevision(asset_id="a", hash="not-hex", mime_type="text/plain")

    def test_job_invalid_state_raises(self):
        with pytest.raises(ValidationError):
            Job(type="ingestion", state="bogus")

    def test_collection_empty_name_raises(self):
        with pytest.raises(ValidationError):
            Collection(name="")


# ===========================================================================
# Hashing: deterministic even on odd byte sequences
# ===========================================================================

class TestHashingEdgeCases:
    def test_empty_bytes_hash(self):
        expected = hashlib.sha256(b"").hexdigest()
        assert sha256_bytes(b"") == expected

    def test_unicode_bytes_hash(self):
        data = "سلام".encode("utf-8")
        assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()

    def test_large_blob_hash(self):
        blob = b"x" * 1_000_000
        assert sha256_bytes(blob) == hashlib.sha256(blob).hexdigest()

    def test_null_byte_sequence(self):
        data = bytes(range(256)) + b"\x00" * 10
        assert sha256_bytes(data) == hashlib.sha256(data).hexdigest()


# ===========================================================================
# Object store: missing keys, empty values, duplicate puts
# ===========================================================================

class TestObjectStoreDirtyPaths:
    def test_get_missing_raises_file_not_found(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        with pytest.raises(FileNotFoundError):
            store.get("f" * 64)

    def test_size_missing_returns_zero(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        assert store.size("a" * 64) == 0

    def test_exists_missing_is_false(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        assert not store.exists("b" * 64)

    def test_delete_missing_returns_false(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        assert store.delete("c" * 64) is False

    def test_duplicate_put_is_deduped(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        h1 = store.put_bytes(b"same")
        h2 = store.put_bytes(b"same")
        assert h1 == h2
        assert store.total_objects() == 1

    def test_empty_bytes_roundtrip(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        h = store.put_bytes(b"")
        assert store.get(h) == b""

    def test_overwrite_returns_new_hash(self, tmp_path):
        store = ObjectStore(tmp_path / "objs")
        h1 = store.put_bytes(b"original")
        h2 = store.put_bytes(b"modified")
        assert h1 != h2
        assert store.total_objects() == 2


# ===========================================================================
# Deduplication and diversity: empty and duplicate-heavy inputs
# ===========================================================================

class TestDeduplicatorDirtyInputs:
    def _hits(self, ids):
        return [SearchHit(id=i, score=float(idx)) for idx, i in enumerate(ids)]

    def test_empty_list(self):
        assert deduplicate([]) == []

    def test_all_duplicates(self):
        hits = self._hits(["a", "a", "a", "a"])
        assert [h.id for h in deduplicate(hits)] == ["a"]

    def test_single_element(self):
        hits = self._hits(["only"])
        assert deduplicate(hits) == hits

    def test_enforce_diversity_empty(self):
        assert enforce_diversity([]) == []

    def test_enforce_diversity_within_limit(self):
        hits = self._hits(["a", "a", "a"])
        assert len(enforce_diversity(hits, max_per_document=5)) == 3

    def test_enforce_diversity_caps_per_document(self):
        hits = self._hits(["a"] * 10)
        result = enforce_diversity(hits, max_per_document=3)
        assert len(result) == 3

    def test_enforce_diversity_custom_key_fn(self):
        hits = [
            SearchHit(id="x1", score=1.0, metadata={"group": "g1"}),
            SearchHit(id="x2", score=2.0, metadata={"group": "g1"}),
            SearchHit(id="x3", score=3.0, metadata={"group": "g2"}),
        ]
        result = enforce_diversity(hits, max_per_document=1, key_fn=lambda h: h.metadata["group"])
        assert len(result) == 2
        assert {h.id for h in result} == {"x1", "x3"}


# ===========================================================================
# Fusion: empty inputs, mismatched weights, extreme top_n
# ===========================================================================

class TestFusionEdgeCases:
    def _hits(self, ids):
        return [SearchHit(id=i, score=float(idx)) for idx, i in enumerate(ids)]

    def test_rrf_empty_groups(self):
        assert rrf_fuse([], top_n=5) == []

    def test_rrf_one_empty_group(self):
        """RRF should still return hits from the non-empty group."""
        result = rrf_fuse([self._hits(["a"]), []], top_n=5)
        assert len(result) == 1
        assert result[0].id == "a"

    def test_linear_empty_groups(self):
        assert linear_fuse([], top_n=5, weights=[]) == []

    def test_linear_mismatched_weights_raises(self):
        hits = self._hits(["a"])
        with pytest.raises(ValueError):
            linear_fuse([hits], top_n=1, weights=[0.5, 0.5])

    def test_linear_top_n_zero_returns_empty(self):
        hits = self._hits(["a", "b"])
        assert linear_fuse([hits], top_n=0) == []

    def test_rrf_top_n_larger_than_universe(self):
        a = self._hits(["a"])
        b = self._hits(["b"])
        fused = rrf_fuse([a, b], top_n=100)
        assert len(fused) <= 2


# ===========================================================================
# Query parser: empty, whitespace, ambiguous embedded filters
# ===========================================================================

class TestQueryParserAmbiguousInputs:
    def setup_method(self):
        self.parser = QueryParser()

    def test_empty_string(self):
        clean, filters = self.parser.parse("")
        assert clean == ""
        assert filters == SearchFilters()

    def test_whitespace_only(self):
        clean, filters = self.parser.parse("   \t\n")
        assert clean.strip() == ""

    def test_embedded_filters_extracted(self):
        clean, filters = self.parser.parse("sensor:Sentinel-2 NDVI")
        assert "Sentinel-2" in (filters.sensors or [])
        assert "NDVI" in clean

    def test_multiple_embedded_filters_same_key(self):
        clean, filters = self.parser.parse("sensor:Sentinel-2 sensor:Landsat-8 query")
        assert sorted(filters.sensors or []) == ["Landsat-8", "Sentinel-2"]

    def test_unknown_filter_token_passthrough(self):
        clean, filters = self.parser.parse("unknown:value hello")
        assert "unknown:value" in clean
        assert filters == SearchFilters()

    def test_none_input(self):
        clean, filters = self.parser.parse(None)
        assert clean == ""
        assert filters == SearchFilters()

    def test_detect_intent_grounded_qa(self):
        assert self.parser.detect_intent("what is NDVI") == "grounded_qa"

    def test_detect_intent_code(self):
        assert self.parser.detect_intent("def compute_ndvi") == "code"

    def test_detect_intent_search_default(self):
        assert self.parser.detect_intent("Sentinel-2 imagery") == "search"


# ===========================================================================
# Spatial filter: dirty bboxes, None fields, extreme values
# ===========================================================================

class TestSpatialFilterDirtyInputs:
    def _hit(self, bbox):
        return SearchHit(id="h1", score=1.0, metadata={"spatial": {"bbox": bbox}})

    def test_none_spatial_filter_returns_all(self):
        hits = [SearchHit(id="h1", score=1.0)]
        assert apply_spatial_filter(hits, None) == hits

    def test_empty_hits_list(self):
        filt = SpatialFilter(bbox=(0, 0, 1, 1))
        assert apply_spatial_filter([], filt) == []

    def test_missing_bbox_on_hit_excluded(self):
        filt = SpatialFilter(bbox=(0, 0, 1, 1))
        hit = SearchHit(id="h1", score=1.0, metadata={})
        assert apply_spatial_filter([hit], filt) == []

    def test_malformed_hit_bbox_excluded(self):
        filt = SpatialFilter(bbox=(0, 0, 1, 1))
        hit = SearchHit(id="h1", score=1.0, metadata={"spatial": {"bbox": [0, 0]}})
        assert apply_spatial_filter([hit], filt) == []

    def test_intersects_disjoint(self):
        filt = SpatialFilter(bbox=(0, 0, 1, 1), op="intersects")
        hit = self._hit([10, 10, 11, 11])
        assert apply_spatial_filter([hit], filt) == []

    def test_intersects_contained(self):
        filt = SpatialFilter(bbox=(0, 0, 10, 10), op="intersects")
        hit = self._hit([2, 2, 3, 3])
        assert apply_spatial_filter([hit], filt) == [hit]

    def test_within_query_smaller_than_hit_fails(self):
        filt = SpatialFilter(bbox=(0, 0, 1, 1), op="within")
        hit = self._hit([0, 0, 5, 5])
        assert apply_spatial_filter([hit], filt) == []

    def test_distance_lte_within_range(self):
        filt = SpatialFilter(bbox=(0, 0, 0.01, 0.01), op="distance_lte", distance_m=50000)
        hit = self._hit([0.001, 0.001, 0.002, 0.002])
        assert apply_spatial_filter([hit], filt) == [hit]

    def test_spatial_ids_empty_on_none(self, tmp_db):
        assert spatial_ids(tmp_db, None) == []

    def test_spatial_ids_empty_on_missing_bbox(self, tmp_db):
        filt = SpatialFilter(geometry_id="missing")
        assert spatial_ids(tmp_db, filt) == []


# ===========================================================================
# Temporal filter: dirty timestamps, missing fields, None ranges
# ===========================================================================

class TestTemporalFilterDirtyInputs:
    def _hit(self, acquired_at=None, observed_at=None, published_at=None, ingested_at=None):
        meta = {}
        if acquired_at is not None:
            meta["spatial"] = {"acquired_at": acquired_at}
        if observed_at is not None:
            meta["observation"] = {"observed_at": observed_at}
        if published_at is not None:
            meta["published_at"] = published_at
        if ingested_at is not None:
            meta["ingested_at"] = ingested_at
        return SearchHit(id="h1", score=1.0, metadata=meta)

    def test_none_temporal_returns_all(self):
        hits = [SearchHit(id="h1", score=1.0)]
        assert apply_temporal_filter(hits, None) == hits

    def test_empty_hits_list(self):
        filt = TemporalFilter(from_="2024-01-01", to="2024-12-31")
        assert apply_temporal_filter([], filt) == []

    def test_hit_missing_field_excluded(self):
        filt = TemporalFilter(from_="2024-01-01", to="2024-12-31", field="acquired_at")
        hit = SearchHit(id="h1", score=1.0, metadata={})
        assert apply_temporal_filter([hit], filt) == []

    def test_within_range_passes(self):
        filt = TemporalFilter(from_="2024-06-01", to="2024-06-30", field="acquired_at")
        hit = self._hit(acquired_at="2024-06-15T10:00:00")
        assert apply_temporal_filter([hit], filt) == [hit]

    def test_before_from_excluded(self):
        filt = TemporalFilter(from_="2024-06-01", to="2024-06-30", field="acquired_at")
        hit = self._hit(acquired_at="2024-05-31T23:59:59")
        assert apply_temporal_filter([hit], filt) == []

    def test_after_to_excluded(self):
        filt = TemporalFilter(from_="2024-06-01", to="2024-06-30", field="acquired_at")
        hit = self._hit(acquired_at="2024-07-01T00:00:00")
        assert apply_temporal_filter([hit], filt) == []

    def test_no_from_uses_only_to(self):
        filt = TemporalFilter(to="2024-06-30", field="acquired_at")
        hit_before = self._hit(acquired_at="2024-05-01")
        hit_after = self._hit(acquired_at="2024-07-01")
        result = apply_temporal_filter([hit_before, hit_after], filt)
        assert result == [hit_before]

    def test_no_to_uses_only_from(self):
        filt = TemporalFilter(from_="2024-06-01", field="acquired_at")
        hit_before = self._hit(acquired_at="2024-05-01")
        hit_after = self._hit(acquired_at="2024-07-01")
        result = apply_temporal_filter([hit_before, hit_after], filt)
        assert result == [hit_after]

    def test_time_in_range_none_value(self):
        assert time_in_range(None, "2024-01-01", "2024-12-31") is False

    def test_time_in_range_no_bounds(self):
        assert time_in_range("2024-06-15", None, None) is True


# ===========================================================================
# Repository edge cases with dirty records
# ===========================================================================

class TestRepositoryDirtyPaths:
    def test_asset_insert_empty_collection_raises(self, tmp_db):
        repo = AssetRepository(tmp_db)
        with pytest.raises((sqlite3.IntegrityError, Exception)):
            repo.insert(Asset(collection_id="missing", kind="document"))

    def test_segment_insert_then_fts_query(self, tmp_db):
        seg_repo = SegmentRepository(tmp_db)
        # Insert required parent records.
        tmp_db.execute("INSERT INTO workspace (id, name, settings) VALUES (?, ?, ?)", ("ws1", "test", "{}"))
        tmp_db.execute("INSERT INTO collection (id, workspace_id, name) VALUES (?, ?, ?)", ("c1", "ws1", "test"))
        tmp_db.execute("INSERT INTO asset (id, collection_id, kind) VALUES (?, ?, ?)", ("a1", "c1", "document"))
        rev_id = "rev_fts"
        tmp_db.execute(
            "INSERT INTO asset_revision (id, asset_id, hash, mime_type, size_bytes, parser_version) VALUES (?, ?, ?, ?, ?, ?)",
            (rev_id, "a1", "0" * 64, "text/plain", 100, "v1"),
        )
        seg = Segment(revision_id=rev_id, text="NDVI vegetation health")
        seg_repo.insert(seg)
        hits = seg_repo.fts_search("vegetation", top_k=5)
        assert any(h.id == seg.id for h in hits)
