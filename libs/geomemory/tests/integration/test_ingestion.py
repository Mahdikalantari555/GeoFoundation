"""Integration tests for the ingestion service pipeline."""

from __future__ import annotations

from pathlib import Path

from geomemory.services.ingestion_service import IngestionService


def _service(temp_workspace) -> IngestionService:
    return IngestionService(temp_workspace.conn, temp_workspace.objects)


class TestIngestionService:
    def test_ingest_markdown_file(self, temp_workspace, sample_markdown):
        col = temp_workspace.create_collection("docs")
        job = _service(temp_workspace).ingest(sample_markdown, col.id)
        assert job.state == "completed"
        assert job.result["segment_count"] > 0
        assert job.result["asset_id"]

    def test_ingest_bytes(self, temp_workspace):
        col = temp_workspace.create_collection("docs")
        job = _service(temp_workspace).ingest(b"raw bytes content", col.id)
        assert job.state == "completed"

    def test_ingest_missing_file_raises(self, temp_workspace):
        col = temp_workspace.create_collection("docs")
        job = _service(temp_workspace).ingest(Path("/nonexistent/x.md"), col.id)
        assert job.state == "failed"

    def test_ingest_missing_collection(self, temp_workspace, sample_markdown):
        job = _service(temp_workspace).ingest(sample_markdown, "missing")
        assert job.state == "failed"

    def test_get_job(self, temp_workspace, sample_markdown):
        svc = _service(temp_workspace)
        col = temp_workspace.create_collection("docs")
        job = svc.ingest(sample_markdown, col.id)
        assert svc.get_job(job.id).id == job.id
