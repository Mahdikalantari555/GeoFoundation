"""Unit tests for core domain models."""

from __future__ import annotations

import numpy as np
import pytest
from pydantic import ValidationError

from geomemory.core.exceptions import SpatialValidationError
from geomemory.core.models import (
    Asset,
    AssetRevision,
    Citation,
    Collection,
    EmbeddingRecord,
    Job,
    QAResult,
    SearchFilters,
    SearchResult,
    Segment,
    SpatialFilter,
    TemporalFilter,
    Workspace,
    WorkspaceSettings,
)


class TestWorkspace:
    def test_defaults(self):
        ws = Workspace(name="test")
        assert ws.id.startswith("ws_")
        assert ws.settings == {}
        assert ws.created_at

    def test_serialization_roundtrip(self):
        ws = Workspace(name="test", settings={"offline": True})
        data = ws.model_dump()
        restored = Workspace(**data)
        assert restored == ws


class TestWorkspaceSettings:
    def test_no_qa_runtime_fields(self):
        """Regression: temperature/max_tokens are QA request params, not
        persisted settings. The dashboard Settings page must not read or
        write them on WorkspaceSettings (caused 'no attribute temperature')."""
        assert "temperature" not in WorkspaceSettings.model_fields
        assert "max_tokens" not in WorkspaceSettings.model_fields

    def test_llm_fields_defaults(self):
        s = WorkspaceSettings(name="ws")
        assert s.llm_provider is None
        assert s.llm_api_base_url is None
        assert s.llm_api_key_env == "GEOMEMORY_LLM_API_KEY"
        assert s.llm_model_id == "kilo-auto/free"
        assert s.llm_context_window == 32768

    def test_llm_settings_roundtrip(self):
        s = WorkspaceSettings(
            name="ws",
            llm_provider="api",
            llm_api_base_url="https://api.kilo.ai/api/gateway/v1",
            llm_model_id="kilo-auto/free",
            llm_context_window=65536,
        )
        data = s.model_dump()
        restored = WorkspaceSettings(**data)
        assert restored == s

    def test_context_window_out_of_range(self):
        with pytest.raises(ValidationError):
            WorkspaceSettings(name="ws", llm_context_window=100)
        with pytest.raises(ValidationError):
            WorkspaceSettings(name="ws", llm_context_window=999999)


class TestCollection:
    def test_defaults(self):
        col = Collection(workspace_id="ws_1", name="papers")
        assert col.id.startswith("col_")
        assert col.archived is False
        assert col.description == ""


class TestAsset:
    def test_kind_validation(self):
        with pytest.raises(ValidationError):
            Asset(collection_id="col_1", kind="invalid")


class TestAssetRevision:
    def test_hash_validation(self):
        with pytest.raises(ValidationError):
            AssetRevision(asset_id="ast_1", hash="not-a-hash", mime_type="text/plain")

    def test_valid_hash(self):
        rev = AssetRevision(
            asset_id="ast_1",
            hash="a" * 64,
            mime_type="text/plain",
            size_bytes=10,
        )
        assert rev.hash == "a" * 64


class TestSegment:
    def test_defaults(self):
        seg = Segment(revision_id="rev_1", text="hello")
        assert seg.segment_type == "paragraph"
        assert seg.locator == {}
        assert seg.neighbor_ids == []

    def test_type_validation(self):
        with pytest.raises(ValidationError):
            Segment(revision_id="rev_1", text="x", segment_type="bogus")


class TestSpatialFilter:
    def test_valid_bbox(self):
        f = SpatialFilter(bbox=(10.0, 20.0, 11.0, 21.0))
        assert f.op == "intersects"

    def test_requires_geometry(self):
        with pytest.raises(ValidationError):
            SpatialFilter()

    def test_inverted_bbox(self):
        with pytest.raises(SpatialValidationError):
            SpatialFilter(bbox=(11.0, 20.0, 10.0, 21.0))

    def test_out_of_range(self):
        with pytest.raises(SpatialValidationError):
            SpatialFilter(bbox=(-200.0, 0.0, 10.0, 10.0))

    def test_antimeridian(self):
        with pytest.raises(SpatialValidationError):
            SpatialFilter(bbox=(179.0, 0.0, -179.0, 10.0))

    def test_distance_lte_requires_distance(self):
        with pytest.raises(ValidationError):
            SpatialFilter(op="distance_lte", bbox=(0.0, 0.0, 1.0, 1.0))


class TestTemporalFilter:
    def test_requires_bound(self):
        with pytest.raises(ValidationError):
            TemporalFilter()

    def test_from_alias(self):
        f = TemporalFilter(from_="2020-01-01", to="2021-01-01")
        assert f.from_ == "2020-01-01"

    def test_inverted_range(self):
        with pytest.raises(ValidationError):
            TemporalFilter(from_="2021-01-01", to="2020-01-01")


class TestSearchFilters:
    def test_defaults(self):
        f = SearchFilters()
        assert f.collections is None
        assert f.spatial is None


class TestEmbeddingRecord:
    def test_from_vector(self):
        vec = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        rec = EmbeddingRecord.from_vector(
            target_id="seg_1",
            target_type="segment",
            space_id="text.nomic.v1",
            model_id="nomic-embed-text-v2-moe",
            vector=vec,
        )
        assert rec.dimension == 3
        assert len(rec.checksum) == 64

    def test_checksum_validation(self):
        with pytest.raises(ValidationError):
            EmbeddingRecord(
                target_id="seg_1",
                target_type="segment",
                space_id="text.nomic.v1",
                model_id="m",
                dimension=3,
                checksum="short",
            )


class TestSearchResult:
    def test_empty_result(self):
        result = SearchResult(query="", query_plan={"intent": "search"})
        assert result.hits == []
        assert result.total_hits == 0


class TestQAResult:
    def test_abstention(self):
        result = QAResult(text="not found", abstained=True, model="none")
        assert result.abstained
        assert result.citations == []


class TestJob:
    def test_defaults(self):
        job = Job(type="ingestion")
        assert job.state == "pending"
        assert job.progress == 0.0

    def test_state_validation(self):
        with pytest.raises(ValidationError):
            Job(type="ingestion", state="bogus")


class TestCitation:
    def test_defaults(self):
        cit = Citation(answer_id="ans_1", segment_id="seg_1")
        assert cit.locator == {}
        assert cit.claim_span is None
