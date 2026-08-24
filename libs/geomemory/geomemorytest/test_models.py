"""Validation edge-case tests for all Pydantic models in ``geomemory.core.models``.

Each test exercises a single contract: default values, valid construction,
validator acceptance, and validator rejection (via ``pytest.raises``).
"""
from __future__ import annotations

import hashlib

import numpy as np
import pytest

from geomemory.core.models import (
    Answer,
    Asset,
    AssetDetail,
    AssetRevision,
    BenchmarkConfig,
    BenchmarkResult,
    Citation,
    Collection,
    Conversation,
    DatasetExample,
    EmbeddingRecord,
    FeedbackEvent,
    GenerationRequest,
    GenerationResult,
    GeoMemoryModel,
    IndexManifest,
    IndexRecord,
    Job,
    Observation,
    QAResult,
    ParsedObject,
    QueryPlan,
    RasterScene,
    RasterTile,
    Relation,
    RetrievalRun,
    SearchFilters,
    SearchHit,
    SearchRequest,
    SearchResult,
    Segment,
    SegmentDraft,
    SourceRef,
    SpatialFilter,
    TemporalFilter,
    Turn,
    VectorLayer,
    Workspace,
    WorkspaceConfig,
    WorkspaceSettings,
)


# ===========================================================================
# Base model contract
# ===========================================================================


class TestGeoMemoryModelBase:
    def test_extra_fields_forbidden(self):
        with pytest.raises(Exception):  # pydantic.ValidationError
            Workspace(name="x", unknown_field="boom")

    def test_model_dump_json_roundtrip(self):
        ws = Workspace(name="test", id="ws_1")
        json_str = ws.model_dump_json()
        assert "ws_1" in json_str

    def test_default_id_prefixes(self):
        ws = Workspace(name="test")
        assert ws.id.startswith("ws_")
        col = Collection(workspace_id="w1", name="c1")
        assert col.id.startswith("col_")
        ast = Asset(collection_id="c1", kind="document")
        assert ast.id.startswith("ast_")
        seg = Segment(revision_id="rev1", text="hello")
        assert seg.id.startswith("seg_")

    def test_utc_now_returns_iso_string(self):
        ws = Workspace(name="test")
        # created_at should be a non-empty ISO-8601 string with Z or +00:00
        assert "T" in ws.created_at


# ===========================================================================
# Filter models
# ===========================================================================


class TestSpatialFilter:
    def test_valid_bbox(self):
        f = SpatialFilter(bbox=(0.0, 0.0, 10.0, 10.0))
        assert f.bbox == (0.0, 0.0, 10.0, 10.0)
        assert f.op == "intersects"

    def test_geometry_id_without_bbox(self):
        f = SpatialFilter(op="within", geometry_id="g1")
        assert f.geometry_id == "g1"
        assert f.bbox is None

    def test_neither_bbox_nor_geometry_id_raises(self):
        with pytest.raises(ValueError, match="requires either bbox or geometry_id"):
            SpatialFilter()

    def test_min_exceeds_max_lon_raises(self):
        with pytest.raises(Exception):
            SpatialFilter(bbox=(10.0, 0.0, 0.0, 10.0))

    def test_min_exceeds_max_lat_raises(self):
        with pytest.raises(Exception):
            SpatialFilter(bbox=(0.0, 10.0, 10.0, 0.0))

    def test_lon_out_of_range_raises(self):
        with pytest.raises(Exception):
            SpatialFilter(bbox=(-200.0, 0.0, 10.0, 10.0))

    def test_lat_out_of_range_raises(self):
        with pytest.raises(Exception):
            SpatialFilter(bbox=(0.0, -100.0, 10.0, 10.0))

    def test_antimeridian_crossing_raises(self):
        # A bbox that genuinely wraps the antimeridian: east > west crossing 180°.
        # Pydantic's order check (min <= max) is bypassed when both are at the edge.
        with pytest.raises(Exception):
            SpatialFilter(bbox=(179.0, 0.0, -179.0, 10.0))

    def test_distance_lte_requires_distance_m(self):
        with pytest.raises(ValueError, match="distance_lte requires distance_m"):
            SpatialFilter(op="distance_lte", geometry_id="g1")

    def test_distance_lte_with_distance_m(self):
        f = SpatialFilter(op="distance_lte", geometry_id="g1", distance_m=5000.0)
        assert f.distance_m == 5000.0

    def test_as_meta_returns_dict(self):
        f = SpatialFilter(bbox=(0.0, 0.0, 10.0, 10.0))
        meta = f.as_meta
        assert meta["op"] == "intersects"
        assert meta["bbox"] == (0.0, 0.0, 10.0, 10.0)


class TestTemporalFilter:
    def test_valid_range(self):
        f = TemporalFilter(field="observed_at", from_="2024-01-01", to="2024-12-31")
        assert f.from_ == "2024-01-01"
        assert f.to == "2024-12-31"

    def test_only_from_required(self):
        f = TemporalFilter(from_="2024-01-01")
        assert f.from_ == "2024-01-01"
        assert f.to is None

    def test_only_to_required(self):
        f = TemporalFilter(to="2024-12-31")
        assert f.to == "2024-12-31"
        assert f.from_ is None

    def test_neither_from_nor_to_raises(self):
        with pytest.raises(ValueError, match="requires at least one"):
            TemporalFilter()

    def test_from_exceeds_to_raises(self):
        with pytest.raises(ValueError, match="from.*exceeds to"):
            TemporalFilter(from_="2024-12-31", to="2024-01-01")

    def test_as_meta_returns_dict(self):
        f = TemporalFilter(from_="2024-01-01", to="2024-12-31")
        meta = f.as_meta
        assert meta["from"] == "2024-01-01"
        assert meta["to"] == "2024-12-31"


class TestSearchFilters:
    def test_defaults_are_none(self):
        f = SearchFilters()
        assert f.collections is None
        assert f.asset_types is None
        assert f.spatial is None
        assert f.temporal is None

    def test_populated_filters(self):
        spatial = SpatialFilter(bbox=(0.0, 0.0, 10.0, 10.0))
        f = SearchFilters(collections=["c1"], sensors=["Sentinel-2"], spatial=spatial)
        assert f.collections == ["c1"]
        assert f.sensors == ["Sentinel-2"]
        assert f.spatial is spatial


# ===========================================================================
# Workspace and configuration
# ===========================================================================


class TestWorkspaceConfig:
    def test_defaults(self):
        cfg = WorkspaceConfig(name="test")
        assert cfg.name == "test"
        assert cfg.language is None
        assert cfg.offline is True
        assert cfg.model_path is None
        assert cfg.default_collection is None

    def test_full_config(self):
        cfg = WorkspaceConfig(
            name="full",
            language="en",
            offline=False,
            model_path="/tmp/model.gguf",
            embedding_path="/tmp/emb.gguf",
            vision_path="/tmp/vis.gguf",
            default_collection="default",
        )
        assert cfg.model_path == "/tmp/model.gguf"
        assert cfg.vision_path == "/tmp/vis.gguf"


class TestWorkspaceSettings:
    def test_defaults(self):
        s = WorkspaceSettings(name="test")
        assert s.name == "test"
        assert s.index_dir == "indexes"
        assert s.objects_dir == "objects"
        assert s.logs_dir == "logs"
        assert s.batch_size == 64
        assert s.thread_count == 4

    def test_custom_dirs(self):
        s = WorkspaceSettings(name="test", index_dir="idx", batch_size=128)
        assert s.index_dir == "idx"
        assert s.batch_size == 128


class TestWorkspace:
    def test_auto_id_prefix(self):
        ws = Workspace(name="test")
        assert ws.id.startswith("ws_")

    def test_settings_default_empty_dict(self):
        ws = Workspace(name="test")
        assert ws.settings == {}


class TestCollection:
    def test_defaults(self):
        col = Collection(workspace_id="w1", name="c1")
        assert col.description == ""
        assert col.archived is False
        assert col.id.startswith("col_")

    def test_archived_true(self):
        col = Collection(workspace_id="w1", name="c1", archived=True)
        assert col.archived is True


# ===========================================================================
# Core entities
# ===========================================================================


class TestAsset:
    def test_valid_kinds(self):
        for kind in ("document", "code", "raster", "vector", "table"):
            a = Asset(collection_id="c1", kind=kind)
            assert a.kind == kind

    def test_invalid_kind_raises(self):
        with pytest.raises(Exception):
            Asset(collection_id="c1", kind="audio")

    def test_defaults(self):
        a = Asset(collection_id="c1", kind="document")
        assert a.title is None
        assert a.current_revision_id is None
        assert a.deleted_at is None
        assert a.metadata == {}


class TestAssetRevision:
    def test_valid_hash_accepted(self):
        h = "a" * 64
        r = AssetRevision(asset_id="a1", hash=h, mime_type="text/plain")
        assert r.hash == h

    def test_uppercase_hash_lowercased(self):
        h = "A" * 64
        r = AssetRevision(asset_id="a1", hash=h, mime_type="text/plain")
        assert r.hash == h.lower()

    def test_short_hash_raises(self):
        with pytest.raises(ValueError, match="64-char hex"):
            AssetRevision(asset_id="a1", hash="abc", mime_type="text/plain")

    def test_non_hex_chars_raises(self):
        with pytest.raises(ValueError, match="64-char hex"):
            AssetRevision(asset_id="a1", hash="g" * 64, mime_type="text/plain")

    def test_defaults(self):
        r = AssetRevision(asset_id="a1", hash="a" * 64, mime_type="text/plain")
        assert r.size_bytes == 0
        assert r.parser_version == "0.1.0"
        assert r.metadata == {}


class TestSegment:
    def test_default_type_paragraph(self):
        seg = Segment(revision_id="r1", text="hello")
        assert seg.segment_type == "paragraph"

    def test_valid_types(self):
        for stype in ("paragraph", "table", "formula", "code_unit", "heading", "cell"):
            seg = Segment(revision_id="r1", text="t", segment_type=stype)
            assert seg.segment_type == stype

    def test_defaults(self):
        seg = Segment(revision_id="r1", text="hello")
        assert seg.parent_section_id is None
        assert seg.neighbor_ids == []
        assert seg.metadata == {}


# ===========================================================================
# Remote sensing models
# ===========================================================================


class TestRasterScene:
    def test_valid_defaults(self):
        scene = RasterScene(revision_id="r1")
        assert scene.crs == "EPSG:4326"
        assert scene.bands == []
        assert scene.bbox == []

    def test_crs_must_start_with_epsg(self):
        with pytest.raises(ValueError, match="crs must start with EPSG"):
            RasterScene(revision_id="r1", crs="WGS84")

    def test_crs_uppercased(self):
        scene = RasterScene(revision_id="r1", crs="epsg:4326")
        assert scene.crs == "EPSG:4326"

    def test_bbox_must_have_4_values(self):
        with pytest.raises(ValueError, match="exactly 4 values"):
            RasterScene(revision_id="r1", bbox=[0.0, 0.0, 10.0])

    def test_valid_bbox(self):
        scene = RasterScene(revision_id="r1", bbox=[0.0, 0.0, 10.0, 20.0])
        assert scene.bbox == [0.0, 0.0, 10.0, 20.0]


class TestRasterTile:
    def test_defaults(self):
        tile = RasterTile(scene_id="s1")
        assert tile.window == {}
        assert tile.transform == []
        assert tile.footprint is None
        assert tile.metadata == {}


class TestVectorLayer:
    def test_valid_geometry_types(self):
        for gtype in ("Point", "LineString", "Polygon", "MultiPoint",
                      "MultiLineString", "MultiPolygon", "GeometryCollection"):
            layer = VectorLayer(revision_id="r1", geometry_type=gtype)
            assert layer.geometry_type == gtype

    def test_invalid_geometry_type_raises(self):
        with pytest.raises(Exception):
            VectorLayer(revision_id="r1", geometry_type="Triangle")

    def test_defaults(self):
        layer = VectorLayer(revision_id="r1", geometry_type="Point")
        assert layer.crs == "EPSG:4326"
        assert layer.feature_count == 0
        assert layer.metadata == {}


# ===========================================================================
# Observation and embedding
# ===========================================================================


class TestObservation:
    def test_defaults(self):
        obs = Observation(subject_id="s1", subject_type="raster_scene", metric="ndvi", value=0.5)
        assert obs.unit is None
        assert obs.valid_from is None
        assert obs.valid_to is None
        assert obs.metadata == {}


class TestEmbeddingRecord:
    def test_from_vector_computes_checksum(self):
        vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        rec = EmbeddingRecord.from_vector(
            target_id="t1", target_type="segment",
            space_id="text.nomic.v1", model_id="m1", vector=vec,
        )
        expected = hashlib.sha256(np.ascontiguousarray(vec, dtype=np.float32).tobytes()).hexdigest()
        assert rec.checksum == expected
        assert rec.dimension == 3

    def test_checksum_validation_rejects_short(self):
        with pytest.raises(ValueError, match="64-char hex"):
            EmbeddingRecord(
                target_id="t1", target_type="segment", space_id="s1",
                model_id="m1", dimension=3, checksum="abc",
            )

    def test_checksum_validation_rejects_non_hex(self):
        with pytest.raises(ValueError, match="64-char hex"):
            EmbeddingRecord(
                target_id="t1", target_type="segment", space_id="s1",
                model_id="m1", dimension=3, checksum="z" * 64,
            )


# ===========================================================================
# Relations
# ===========================================================================


class TestRelation:
    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            Relation(source_id="s1", predicate="p1", target_id="t1", confidence=1.5)
        with pytest.raises(Exception):
            Relation(source_id="s1", predicate="p1", target_id="t1", confidence=-0.1)

    def test_defaults(self):
        r = Relation(source_id="s1", predicate="p1", target_id="t1")
        assert r.confidence == 1.0
        assert r.extractor == "manual"
        assert r.evidence_id is None
        assert r.id.startswith("rel_")


# ===========================================================================
# Conversation, retrieval, QA
# ===========================================================================


class TestConversation:
    def test_defaults(self):
        conv = Conversation(workspace_id="w1")
        assert conv.collection_scope == []
        assert conv.title is None
        assert conv.id.startswith("conv_")


class TestTurn:
    def test_valid_roles(self):
        for role in ("user", "system", "assistant"):
            t = Turn(conversation_id="c1", role=role, content="hi")
            assert t.role == role

    def test_invalid_role_raises(self):
        with pytest.raises(Exception):
            Turn(conversation_id="c1", role="human", content="hi")


class TestRetrievalRun:
    def test_defaults(self):
        run = RetrievalRun(query="test")
        assert run.query_plan == {}
        assert run.filters == {}
        assert run.config == {}
        assert run.candidates == []
        assert run.results == []
        assert run.latency_ms is None
        assert run.id.startswith("run_")


class TestAnswer:
    def test_defaults(self):
        ans = Answer(model="m1", prompt_hash="h1", text="hello")
        assert ans.abstained is False
        assert ans.id.startswith("ans_")


class TestCitation:
    def test_defaults(self):
        cit = Citation(answer_id="a1", segment_id="s1")
        assert cit.locator == {}
        assert cit.claim_span is None
        assert cit.id.startswith("cit_")


class TestSearchHit:
    def test_defaults(self):
        hit = SearchHit(id="h1")
        assert hit.score == 0.0
        assert hit.sparse_score is None
        assert hit.dense_score is None
        assert hit.text == ""
        assert hit.metadata == {}
        assert hit.locator == {}


class TestSearchResult:
    def test_valid_result(self):
        hit = SearchHit(id="h1", score=0.9)
        plan = QueryPlan(mode="hybrid")
        result = SearchResult(query="q", query_plan=plan, hits=[hit], total_hits=1)
        assert result.total_hits == 1
        assert len(result.hits) == 1


class TestQAResult:
    def test_abstained_defaults(self):
        qa = QAResult(text="", abstained=True, abstention_reason="no model")
        assert qa.abstained is True
        assert qa.abstention_reason == "no model"
        assert qa.citations == []
        assert qa.sources == []

    def test_successful_answer(self):
        hit = SearchHit(id="h1", score=0.9)
        qa = QAResult(text="NDVI", sources=[hit], abstained=False)
        assert qa.abstained is False
        assert len(qa.sources) == 1


# ===========================================================================
# Feedback and evaluation
# ===========================================================================


class TestFeedbackEvent:
    def test_valid_event(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        fb = FeedbackEvent(
            target_type="answer", target_id="a1", label="answer_rating",
            payload={"rating": 5}, created_at=now,
        )
        assert fb.actor == "user"
        assert fb.payload == {"rating": 5}
        assert fb.id.startswith("fb_")


class TestDatasetExample:
    def test_valid_review_states(self):
        for state in ("pending", "accepted", "rejected"):
            ds = DatasetExample(task_type="rag_eval", review_state=state)
            assert ds.review_state == state

    def test_invalid_review_state_raises(self):
        with pytest.raises(Exception):
            DatasetExample(task_type="rag_eval", review_state="maybe")

    def test_defaults(self):
        ds = DatasetExample(task_type="rag_eval")
        assert ds.source_feedback_ids == []
        assert ds.review_state == "pending"
        assert ds.reviewer_id is None
        assert ds.version == 1
        assert ds.dataset_card is None
        assert ds.id.startswith("dsx_")


class TestJob:
    def test_valid_states(self):
        for state in ("pending", "running", "completed", "failed", "cancelled"):
            job = Job(type="ingestion", state=state)
            assert job.state == state

    def test_invalid_state_raises(self):
        with pytest.raises(Exception):
            Job(type="ingestion", state="unknown")

    def test_progress_bounds(self):
        with pytest.raises(Exception):
            Job(type="ingestion", progress=-0.1)
        with pytest.raises(Exception):
            Job(type="ingestion", progress=1.5)

    def test_defaults(self):
        job = Job(type="ingestion")
        assert job.state == "pending"
        assert job.progress == 0.0
        assert job.input == {}
        assert job.result is None
        assert job.error is None
        assert job.checkpoint is None
        assert job.id.startswith("job_")


# ===========================================================================
# Ingestion pipeline models
# ===========================================================================


class TestSourceRef:
    def test_path_only(self):
        s = SourceRef(path="/tmp/file.txt")
        assert s.path == "/tmp/file.txt"
        assert s.url is None
        assert s.content_bytes is None

    def test_url_only(self):
        s = SourceRef(url="https://example.com/doc")
        assert s.url == "https://example.com/doc"

    def test_content_bytes_only(self):
        s = SourceRef(content_bytes=b"raw data")
        assert s.content_bytes == b"raw data"

    def test_multiple_sources_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            SourceRef(path="/tmp", url="https://x.com")

    def test_no_source_raises(self):
        with pytest.raises(ValueError, match="exactly one"):
            SourceRef()


class TestParsedObject:
    def test_defaults(self):
        src = SourceRef(path="/tmp/f.txt")
        obj = ParsedObject(source=src, mime_type="text/plain", title="doc")
        assert obj.text == ""
        assert obj.metadata == {}
        assert obj.raw is None


class TestSegmentDraft:
    def test_valid_types(self):
        for stype in ("paragraph", "table", "formula", "code_unit", "heading", "cell"):
            d = SegmentDraft(text="t", segment_type=stype)
            assert d.segment_type == stype

    def test_defaults(self):
        d = SegmentDraft(text="hello")
        assert d.locator == {}
        assert d.parent_section_id is None
        assert d.neighbor_ids == []
        assert d.metadata == {}


class TestIndexRecord:
    def test_defaults(self):
        rec = IndexRecord(id="r1", text="hello")
        assert rec.metadata == {}
        assert rec.embedding is None
        assert rec.space_id == "text.nomic.v1"


class TestSearchRequest:
    def test_defaults(self):
        req = SearchRequest(query="test")
        assert req.top_k == 20
        assert req.top_n == 5
        assert req.mode == "hybrid"
        assert req.fusion == "rrf"
        assert isinstance(req.filters, SearchFilters)


class TestGenerationRequest:
    def test_defaults(self):
        hit = SearchHit(id="h1")
        req = GenerationRequest(prompt="q?", context=[hit])
        assert req.max_tokens == 512
        assert req.temperature == 0.2
        assert req.stop_sequences == []


class TestGenerationResult:
    def test_defaults(self):
        res = GenerationResult(text="ans", prompt_hash="h1", model_id="m1")
        assert res.tokens_used == 0
        assert res.latency_ms == 0
        assert res.abstained is False


# ===========================================================================
# Index manifest
# ===========================================================================


class TestIndexManifest:
    def test_defaults(self):
        m = IndexManifest(space_id="text.nomic.v1", model_id="m1", dimension=768)
        assert m.model_revision == ""
        assert m.normalization == "l2"
        assert m.chunker == "header_then_token"
        assert m.chunk_size == 1000
        assert m.chunk_overlap == 150
        assert m.doc_count == 0

    def test_to_json_returns_string(self):
        m = IndexManifest(space_id="s1", model_id="m1", dimension=768)
        json_str = m.to_json()
        assert "space_id" in json_str
        assert "s1" in json_str


# ===========================================================================
# Asset detail
# ===========================================================================


class TestAssetDetail:
    def test_empty_detail(self):
        detail = AssetDetail(asset=Asset(collection_id="c1", kind="document"))
        assert detail.revision is None
        assert detail.segments == []
        assert detail.scenes == []
        assert detail.layers == []
        assert detail.observations == []
        assert detail.embeddings == []


# ===========================================================================
# Benchmark config and result
# ===========================================================================


class TestBenchmarkConfig:
    def test_defaults(self):
        cfg = BenchmarkConfig()
        assert cfg.seeds == [42]
        assert cfg.top_k_values == [5, 10, 20]
        assert cfg.mode == "hybrid"
        assert cfg.output_dir is None

    def test_custom_values(self):
        cfg = BenchmarkConfig(mode="sparse", seeds=[1, 2, 3], output_dir="/tmp")
        assert cfg.mode == "sparse"
        assert cfg.seeds == [1, 2, 3]
        assert cfg.output_dir == "/tmp"

    def test_invalid_mode_raises(self):
        with pytest.raises(Exception):
            BenchmarkConfig(mode="invalid")


class TestBenchmarkResult:
    def test_defaults(self):
        res = BenchmarkResult()
        assert res.name == "benchmark"
        assert res.metrics == {}
        assert res.report == ""

    def test_with_metrics(self):
        cfg = BenchmarkConfig(mode="hybrid")
        res = BenchmarkResult(
            name="eval1",
            metrics={"recall@10": {"mean": 0.9}},
            report="all good",
            config=cfg,
        )
        assert res.metrics["recall@10"]["mean"] == 0.9
        assert res.report == "all good"


# ===========================================================================
# Query plan
# ===========================================================================


class TestQueryPlan:
    def test_defaults(self):
        plan = QueryPlan()
        assert plan.intent == "search"
        assert plan.mode == "hybrid"
        assert plan.spaces == []
        assert plan.top_k == 20
        assert plan.top_n == 5

    def test_custom_plan(self):
        plan = QueryPlan(intent="grounded_qa", mode="dense", spaces=["text.nomic.v1"])
        assert plan.intent == "grounded_qa"
        assert plan.spaces == ["text.nomic.v1"]


# ===========================================================================
# JSON serialization helpers
# ===========================================================================


class TestJSONHelpers:
    def test_spatial_filter_serializable(self):
        f = SpatialFilter(bbox=(0.0, 0.0, 10.0, 10.0))
        json_str = f.model_dump_json()
        assert "intersects" in json_str

    def test_search_result_json(self):
        hit = SearchHit(id="h1", score=0.9, text="sample text")
        plan = QueryPlan(mode="hybrid")
        result = SearchResult(query="q", query_plan=plan, hits=[hit])
        json_str = result.model_dump_json()
        assert "sample text" in json_str

    def test_embedding_record_from_vector_stable_checksum(self):
        """Same vector produces same checksum (deterministic hash)."""
        vec = np.array([0.5, -0.5, 1.0], dtype=np.float32)
        r1 = EmbeddingRecord.from_vector("t1", "seg", "s1", "m1", vec)
        r2 = EmbeddingRecord.from_vector("t1", "seg", "s1", "m1", vec)
        assert r1.checksum == r2.checksum
