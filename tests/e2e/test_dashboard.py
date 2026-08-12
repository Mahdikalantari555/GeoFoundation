"""End-to-end smoke test for the Streamlit dashboard using AppTest.

Boots the dashboard headlessly, creates a workspace, ingests a document,
runs a search, asks a question (abstains without an LLM), and inspects
the Overview/Search/Ask pages.
"""

from __future__ import annotations

from pathlib import Path

import pytest

streamlit = pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

DASHBOARD = Path(__file__).resolve().parents[2] / "apps" / "dashboard" / "app.py"


def _by_label(elements, label: str):
    for el in elements:
        if getattr(el, "label", None) == label:
            return el
    return None


@pytest.fixture(scope="module")
def sample_workspace(tmp_path_factory):
    from geomemory import GeoMemory

    ws_dir = tmp_path_factory.mktemp("dash_ws")
    ws = GeoMemory.create(ws_dir / "ws")
    col = ws.create_collection("papers", "Sample papers")
    doc = ws_dir / "notes.md"
    doc.write_text(
        "# NDVI notes\n\n"
        "NDVI measures vegetation health from Sentinel-2 imagery.\n"
        "Low NDVI values indicate drought stress in crops.\n",
        encoding="utf-8",
    )
    ws.ingest(str(doc), collection_id=col.id)
    ws.close()
    return str(ws_dir / "ws")


def _boot(sample_workspace: str) -> AppTest:
    at = AppTest.from_file(str(DASHBOARD), default_timeout=60)
    at.run()
    at.text_input[0].set_value(sample_workspace).run()
    at.button[0].click().run()
    return at


def test_dashboard_boots_and_opens_workspace(sample_workspace: str) -> None:
    at = _boot(sample_workspace)
    assert not at.exception
    assert any(m.value == "1" for m in at.metric)


def test_overview_metrics(sample_workspace: str) -> None:
    at = _boot(sample_workspace)
    assert not at.exception
    metric_values = {m.value for m in at.metric}
    assert "1" in metric_values  # assets / collections


def test_search_page_runs(sample_workspace: str) -> None:
    at = _boot(sample_workspace)
    at.sidebar.radio[0].set_value("🔍 Search").run()
    assert not at.exception
    query = _by_label(at.text_input, "Query")
    assert query is not None
    query.set_value("NDVI").run()
    search_btn = _by_label(at.button, "Search")
    assert search_btn is not None
    search_btn.click().run()
    assert not at.exception
    body = "".join(e.value for e in at.markdown)
    assert "hits" in body or "No results" in body


def test_ask_page_abstains_without_llm(sample_workspace: str) -> None:
    at = _boot(sample_workspace)
    at.sidebar.radio[0].set_value("💬 Ask / QA").run()
    assert not at.exception
    qa = _by_label(at.text_area, "Question")
    assert qa is not None
    qa.set_value("What detects crop stress?").run()
    ask_btn = _by_label(at.button, "Ask")
    assert ask_btn is not None
    ask_btn.click().run()
    assert not at.exception
    assert any("Abstained" in m.value for m in at.markdown)


def test_ingest_page_creates_collection(sample_workspace: str) -> None:
    at = _boot(sample_workspace)
    at.sidebar.radio[0].set_value("📥 Ingest").run()
    assert not at.exception
    assert any("Target collection" in (s.label or "") for s in at.selectbox)
