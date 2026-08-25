"""Golden ingestion tests: known fixtures must produce stable, searchable assets.

PDF/DOCX tests are skipped when their optional parser dependencies are not
installed; the text-based fixtures always run.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _ingest(ws, path):
    col = ws.create_collection("golden")
    job = ws.ingest(path, collection_id=col.id)
    assert job.state == "completed"
    assert job.result["asset_id"]
    assert job.result["segment_count"] > 0
    return col, job


class TestGoldenTextFixtures:
    @pytest.mark.parametrize("name", ["rs_notes.md", "ndvi.py", "analysis.ipynb"])
    def test_text_fixture_ingests(self, temp_workspace, name):
        col, job = _ingest(temp_workspace, FIXTURES / name)
        assert temp_workspace.inspect(job.result["asset_id"]).segments

    def test_golden_markdown_searchable(self, temp_workspace):
        col, job = _ingest(temp_workspace, FIXTURES / "rs_notes.md")
        result = temp_workspace.search("NDVI vegetation health")
        assert result.total_hits > 0

    def test_golden_python_searchable(self, temp_workspace):
        col, job = _ingest(temp_workspace, FIXTURES / "ndvi.py")
        result = temp_workspace.search("normalized difference vegetation index")
        assert result.total_hits > 0

    def test_golden_notebook_searchable(self, temp_workspace):
        col, job = _ingest(temp_workspace, FIXTURES / "analysis.ipynb")
        result = temp_workspace.search("crop stress")
        assert result.total_hits > 0

    def test_redingest_is_deduped(self, temp_workspace):
        col, job = _ingest(temp_workspace, FIXTURES / "rs_notes.md")
        job2 = temp_workspace.ingest(FIXTURES / "rs_notes.md", collection_id=col.id)
        assert job2.result["skipped"] is True
        assert len(temp_workspace.list_assets(col.id)) == 1


def _has_pymupdf() -> bool:
    try:
        import fitz  # noqa: F401
        return True
    except ImportError:
        return False


def _has_python_docx() -> bool:
    try:
        import docx  # noqa: F401
        return True
    except ImportError:
        return False


class TestGoldenBinaryFixtures:
    @pytest.mark.skipif(
        not _has_pymupdf(), reason="pymupdf not installed"
    )
    def test_pdf_ingests(self, temp_workspace):
        col, job = _ingest(temp_workspace, FIXTURES / "flood_report.pdf")
        result = temp_workspace.search("Sentinel-1 SAR")
        assert result.total_hits > 0

    @pytest.mark.skipif(
        not _has_python_docx(), reason="python-docx not installed"
    )
    def test_docx_ingests(self, temp_workspace):
        col, job = _ingest(temp_workspace, FIXTURES / "landcover.docx")
        result = temp_workspace.search("Sentinel-2 classification")
        assert result.total_hits > 0
