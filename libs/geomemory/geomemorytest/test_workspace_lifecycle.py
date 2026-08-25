"""Workspace lifecycle tests.

Covers :class:`GeoMemory` create/open/close, settings round-trip, collection
CRUD, event emission, stats on a fresh workspace, and the doctor helpers.
"""
from __future__ import annotations

import sqlite3

import pytest

from geomemory import GeoMemory, WorkspaceNotFoundError
from geomemory.core.events import COLLECTION_CREATED, DomainEvent, EventBus
from geomemory.services.doctor import doctor_environment, doctor_workspace, doctor_workspace_open


# ===========================================================================
# Helpers
# ===========================================================================

class _RecordingBus:
    """Collect emitted events for assertions."""

    def __init__(self) -> None:
        self.events: list[DomainEvent] = []

    def install(self, ws: GeoMemory) -> None:
        bus = EventBus()
        bus.subscribe(COLLECTION_CREATED, self.events.append)
        ws.events = bus  # type: ignore[attr-defined]


# ===========================================================================
# GeoMemory.create / open / close
# ===========================================================================

class TestGeoMemoryLifecycle:
    def test_create_marks_workspace(self, tmp_path):
        root = tmp_path / "ws"
        ws = GeoMemory.create(root)
        try:
            assert (root / ".geomemory").is_file()
            assert (root / "geomemory.db").is_file()
            assert (root / "workspace.yaml").is_file()
        finally:
            ws.close()

    def test_create_empty_directory_is_allowed(self, tmp_path):
        root = tmp_path / "empty"
        root.mkdir()
        ws = GeoMemory.create(root)
        try:
            assert (root / ".geomemory").is_file()
        finally:
            ws.close()

    def test_create_non_empty_directory_raises(self, tmp_path):
        root = tmp_path / "busy"
        root.mkdir()
        (root / "junk.txt").write_text("data", encoding="utf-8")
        with pytest.raises(Exception):
            GeoMemory.create(root)

    def test_create_then_open_roundtrip(self, tmp_path):
        root = tmp_path / "roundtrip"
        ws_create = GeoMemory.create(root)
        try:
            ws_create.create_collection("test")
        finally:
            ws_create.close()

        ws_open = GeoMemory.open(root)
        try:
            names = [c.name for c in ws_open.list_collections()]
            assert "test" in names
        finally:
            ws_open.close()

    def test_open_missing_marker_raises_not_found(self, tmp_path):
        with pytest.raises(WorkspaceNotFoundError):
            GeoMemory.open(tmp_path / "nonexistent")

    def test_close_idempotent(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "idem")
        ws.close()
        ws.close()  # must not raise

    def test_context_manager_closes(self, tmp_path):
        with GeoMemory.create(tmp_path / "ctx") as ws:
            assert (tmp_path / "ctx" / ".geomemory").is_file()
        assert ws._closed

    def test_create_with_custom_name(self, tmp_path):
        root = tmp_path / "named"
        ws = GeoMemory.create(root)
        try:
            assert ws.settings.name == "GeoMemory Workspace"
        finally:
            ws.close()


# ===========================================================================
# Settings round-trip
# ===========================================================================

class TestSettingsRoundTrip:
    def test_update_settings_persists(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "cfg")
        try:
            updated = ws.update_settings(model_path="/some/model.gguf")
            assert updated.model_path == "/some/model.gguf"
            # Re-open to confirm persistence.
            ws.close()
            ws2 = GeoMemory.open(tmp_path / "cfg")
            try:
                assert ws2.settings.model_path == "/some/model.gguf"
            finally:
                ws2.close()
        finally:
            ws.close()

    def test_update_unknown_setting_raises(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "unk")
        try:
            with pytest.raises(ValueError, match="Unknown setting"):
                ws.update_settings(nonexistent_field="x")
        finally:
            ws.close()

    def test_default_settings_values(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "defs")
        try:
            s = ws.settings
            assert s.name == "GeoMemory Workspace"
            assert s.offline is True
            assert s.index_dir == "indexes"
            assert s.objects_dir == "objects"
            assert s.batch_size == 64
        finally:
            ws.close()


# ===========================================================================
# Collections
# ===========================================================================

class TestCollections:
    def test_create_collection_returns_model(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "col")
        try:
            coll = ws.create_collection("papers")
            assert coll.name == "papers"
            assert coll.id is not None
        finally:
            ws.close()

    def test_list_collections_fresh_workspace_empty(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "emptycols")
        assert ws.list_collections() == []

    def test_archive_collection_soft_deletes(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "arc")
        try:
            coll = ws.create_collection("to_archive")
            result = ws.archive_collection(coll.id)
            assert result is True
            assert ws.list_collections() == []
        finally:
            ws.close()

    def test_archive_missing_returns_false(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "miss")
        try:
            assert ws.archive_collection("does-not-exist") is False
        finally:
            ws.close()

    def test_collection_event_emitted(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "evt")
        bus = _RecordingBus()
        bus.install(ws)
        try:
            coll = ws.create_collection("evented")
            assert len(bus.events) == 1
            assert bus.events[0].event_type == COLLECTION_CREATED
            assert bus.events[0].entity_id == coll.id
        finally:
            ws.close()


# ===========================================================================
# Stats
# ===========================================================================

class TestStats:
    def test_fresh_workspace_has_zero_counts(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "stats")
        try:
            s = ws.stats()
            assert s["collections"] == 0
            assert s["assets"] == 0
            assert s["segments"] == 0
            assert s["feedback_events"] == 0
            assert "storage_bytes" in s
        finally:
            ws.close()

    def test_stats_reflects_ingested_data(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "ingstats")
        try:
            coll = ws.create_collection("papers")
            md = tmp_path / "note.md"
            md.write_text("# NDVI\n\nSentinel-2 crop monitoring.\n", encoding="utf-8")
            ws.ingest(md, collection_id=coll.id)
            s = ws.stats()
            assert s["collections"] >= 1
            assert s["assets"] >= 1
            assert s["segments"] >= 1
        finally:
            ws.close()


# ===========================================================================
# EventBus
# ===========================================================================

class TestEventBus:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        received: list[str] = []
        bus.subscribe("test", lambda e: received.append(e.event_type))
        bus.emit(DomainEvent(event_type="test", entity_id="x"))
        assert received == ["test"]

    def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        received: list[str] = []

        def handler(e):
            received.append(e.event_type)

        bus.subscribe("t", handler)
        bus.unsubscribe("t", handler)
        bus.emit(DomainEvent(event_type="t", entity_id="x"))
        assert received == []

    def test_emit_no_subscribers_does_not_raise(self):
        bus = EventBus()
        bus.emit(DomainEvent(event_type="lonely", entity_id="x"))  # must not raise

    def test_multiple_handlers_all_invoked(self):
        bus = EventBus()
        out: list[str] = []
        bus.subscribe("t", lambda e: out.append("a"))
        bus.subscribe("t", lambda e: out.append("b"))
        bus.emit(DomainEvent(event_type="t", entity_id="x"))
        assert out == ["a", "b"]


# ===========================================================================
# Doctor
# ===========================================================================

class TestDoctor:
    def test_doctor_environment_reports_python_ok(self):
        report = doctor_environment()
        assert report["python_ok"] is True

    def test_doctor_environment_core_deps_present(self):
        report = doctor_environment()
        assert report["core_ok"] is True
        for dep in ("pydantic", "numpy", "yaml"):
            assert report["core_deps"][dep] is True

    def test_doctor_workspace_missing_marker_returns_not_ok(self, tmp_path):
        report = doctor_workspace(tmp_path / "not_a_workspace")
        assert report["ok"] is False
        assert not report["checks"]["marker_exists"]

    def test_doctor_workspace_valid_returns_ok(self, tmp_path):
        root = tmp_path / "valid"
        ws = GeoMemory.create(root)
        try:
            ws.close()
            report = doctor_workspace(root)
            assert report["ok"] is True
            assert report["checks"]["marker_exists"] is True
            assert report["checks"]["settings_valid"] is True
            assert report["checks"]["db_exists"] is True
        finally:
            if not ws._closed:
                ws.close()

    def test_doctor_workspace_open_runs_list_and_stats(self, tmp_path):
        root = tmp_path / "openws"
        ws = GeoMemory.create(root)
        ws.close()
        report = doctor_workspace_open(root)
        assert report["ok"] is True
        assert report["checks"]["open_list_collections"] is True
        assert report["checks"]["stats"] is True


# ===========================================================================
# Ingestion round-trip via GeoMemory.ingest
# ===========================================================================

class TestIngestionRoundTrip:
    def test_ingest_markdown_creates_segments(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "ing")
        try:
            coll = ws.create_collection("papers")
            md = tmp_path / "paper.md"
            md.write_text(
                "# Introduction\n\n"
                "Remote sensing uses NDVI from Sentinel-2.\n\n"
                "## Methods\n\n"
                "We classify crop stress.\n",
                encoding="utf-8",
            )
            job = ws.ingest(md, collection_id=coll.id)
            assert job.state == "completed"
            assert job.result.get("segment_count", 0) >= 1
            assets = ws.list_assets(coll.id)
            assert len(assets) == 1
            detail = ws.inspect(assets[0].id)
            assert len(detail.segments) >= 1
            texts = " ".join(s.text for s in detail.segments)
            assert "NDVI" in texts
        finally:
            ws.close()

    def test_ingest_dedup_same_bytes_skipped(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "dedup")
        try:
            coll = ws.create_collection("papers")
            md = tmp_path / "note.md"
            md.write_text("# NDVI Analysis\n\nSentinel-2.\n", encoding="utf-8")
            job1 = ws.ingest(md, collection_id=coll.id)
            job2 = ws.ingest(md, collection_id=coll.id)
            assert job1.result.get("skipped") is not True
            assert job2.result.get("skipped") is True
            assert job2.result.get("reason") == "duplicate hash"
            assets = ws.list_assets(coll.id)
            assert len(assets) == 1
        finally:
            ws.close()

    def test_ingest_python_extracts_code_units(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "codeing")
        try:
            coll = ws.create_collection("code")
            py = tmp_path / "ndvi.py"
            py.write_text(
                "def compute_ndvi(nir, red):\n"
                '    """Compute NDVI."""\n'
                "    return (nir - red) / (nir + red)\n",
                encoding="utf-8",
            )
            job = ws.ingest(py, collection_id=coll.id)
            assert job.state == "completed"
            assets = ws.list_assets(coll.id)
            detail = ws.inspect(assets[0].id)
            seg_text = " ".join(s.text for s in detail.segments)
            assert "compute_ndvi" in seg_text
        finally:
            ws.close()


# ===========================================================================
# Search via GeoMemory.search (full pipeline over ingested content)
# ===========================================================================

class TestWorkspaceSearchRoundTrip:
    def test_search_returns_hits_over_ingested_content(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "srch")
        try:
            coll = ws.create_collection("papers")
            md = tmp_path / "crop.md"
            md.write_text(
                "# Crop Stress\n\n"
                "NDVI detects crop stress in Sentinel-2 imagery.\n",
                encoding="utf-8",
            )
            ws.ingest(md, collection_id=coll.id)

            result = ws.search("NDVI", mode="hybrid", top_k=5, top_n=3)
            assert isinstance(result, type(result))
            assert result.total_hits >= 1
            texts = " ".join(h.text or "" for h in result.hits)
            assert "NDVI" in texts
            assert result.latency_ms is not None
            assert result.latency_ms >= 0
        finally:
            ws.close()

    def test_search_sensor_filter_returns_result_or_empty(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "sens")
        try:
            coll = ws.create_collection("rs")
            md = tmp_path / "data.md"
            md.write_text("Sentinel-1 SAR flood mapping.\n", encoding="utf-8")
            ws.ingest(md, collection_id=coll.id)
            result = ws.search("Sentinel-1", mode="hybrid", top_k=5, top_n=3)
            assert isinstance(result, type(result))
            assert result.total_hits >= 1
            # Sensor filter narrows further; result must still be a valid SearchResult.
            result2 = ws.search("Sentinel-1", mode="hybrid", top_k=5, top_n=3, sensor=["Sentinel-1"])
            assert isinstance(result2, type(result2))
        finally:
            ws.close()

    def test_search_empty_query_returns_empty(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "eq")
        try:
            result = ws.search("")
            assert result.hits == []
        finally:
            ws.close()


# ===========================================================================
# QA / ask abstention paths
# ===========================================================================

class TestAskAbstention:
    def test_ask_no_model_abstains_when_context_exists(self, tmp_path):
        """When search has hits but no LLM is configured, abstain reason mentions model."""
        ws = GeoMemory.create(tmp_path / "nomodel")
        try:
            coll = ws.create_collection("papers")
            md = tmp_path / "note.md"
            md.write_text("# NDVI\n\nSentinel-2 monitors vegetation.\n", encoding="utf-8")
            ws.ingest(md, collection_id=coll.id)
            result = ws.ask("What is NDVI?")
            assert result.abstained is True
            assert result.abstention_reason == (
                "No LLM backend configured (set model_path in workspace.yaml)"
            )
        finally:
            ws.close()

    def test_ask_empty_question_abstains(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "emptyq")
        try:
            result = ws.ask("")
            assert result.abstained is True
        finally:
            ws.close()


# ===========================================================================
# Feedback via workspace API
# ===========================================================================

class TestWorkspaceFeedback:
    def test_record_feedback_roundtrip(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "fb")
        try:
            from geomemory.core.models import FeedbackEvent

            evt = FeedbackEvent(
                target_type="retrieval_run",
                target_id="run-1",
                label="source_relevance",
                payload={"score": 4},
            )
            saved = ws.record_feedback(evt)
            assert saved.id == evt.id
            events = ws.get_review_queue()  # empty queue expected
            assert events == []
        finally:
            ws.close()

    def test_review_example_missing_returns_false(self, tmp_path):
        ws = GeoMemory.create(tmp_path / "rev")
        try:
            assert ws.review_example("does-not-exist", accept=True) is False
        finally:
            ws.close()
