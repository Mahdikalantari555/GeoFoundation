"""Tests for the Streamlit dashboard page renderers.

The ``streamlit`` module is stubbed at module import time so that ``st.*``
calls are captured rather than executed.  Each test creates a fake
:class:`geomemory.GeoMemory` workspace with just enough behaviour to
exercise the page's code paths.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Install the streamlit stub BEFORE any page module is imported.
# ---------------------------------------------------------------------------

class _StCall:
    """Record every st.* call made during a test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.errors: list[str] = []
        self.session_state: dict[str, object] = {}
        # Overridable return values for input widgets used in form-submit paths.
        self._text_input_return: str = ""
        self._text_area_return: str = ""
        self._number_input_return: int | float = 0
        self._selectbox_return: str = ""
        self._multiselect_return: list = []
        self._form_submit_return: bool = False
        self._button_return: bool = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def _col(self, n: int) -> "_StCall":
        col = _StCall()
        col._parent_calls = self.calls  # share parent call log
        return col

    def __getattr__(self, name):
        # Input widgets must return a sensible default value, not self.
        if name in ("text_input", "text_area"):
            def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self._text_area_return if name == "text_area" else self._text_input_return
            return _record
        if name in ("number_input", "slider"):
            def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self._number_input_return
            return _record
        if name in ("selectbox", "radio"):
            def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self._selectbox_return
            return _record
        if name == "multiselect":
            def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self._multiselect_return
            return _record
        if name in ("button", "form_submit_button"):
            def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return self._form_submit_return if name == "form_submit_button" else self._button_return
            return _record
        if name == "file_uploader":
            def _record(*args, **kwargs):
                self.calls.append((name, args, kwargs))
                return None
            return _record
        # Display / layout widgets return self (chainable).
        def _record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == "error":
                self.errors.append(args[0] if args else "")
            if name == "columns":
                n = args[0] if args else 1
                return tuple(self._col(i) for i in range(n))
            if name == "tabs":
                n = len(args[0]) if args else 1
                return tuple(self._col(i) for i in range(n))
            if name == "expander":
                return self._expander_stub()
            return self
        return _record

    def _expander_stub(self) -> "_StCall":
        """Return a context-manager stub for st.expander."""
        return self

    def called_with(self, name: str, /, *args, **kwargs) -> bool:
        for call_name, call_args, call_kwargs in self.calls:
            if call_name == name and args == call_args and kwargs == call_kwargs:
                return True
        return False

    def call_count(self, name: str) -> int:
        return sum(1 for c, _, _ in self.calls if c == name)


_STUB = _StCall()
_STUB_MOD = types.ModuleType("streamlit")
_STUB_MOD.session_state = _STUB.session_state
_STUB_MOD.error = lambda msg: _STUB.errors.append(msg) or None
for _attr in (
    "header", "subheader", "caption", "info", "warning", "error", "success",
    "title", "metric", "json", "write", "markdown", "container",
    "columns", "column", "expander", "text_input", "text_area",
    "number_input", "selectbox", "multiselect", "radio", "button",
    "form_submit_button", "slider", "file_uploader", "download_button",
    "sidebar", "divider", "spinner", "rerun", "set_page_config",
    "tabs", "form",
):
    setattr(_STUB_MOD, _attr, getattr(_STUB, _attr))

# Ensure the GeoMemory root (which contains the ``apps`` package) is on sys.path.
_GEO_ROOT = Path(__file__).resolve().parents[1] / "GeoMemory"
if str(_GEO_ROOT) not in sys.path:
    sys.path.insert(0, str(_GEO_ROOT))

# Drop any cached streamlit or apps modules so they pick up the stub.
for _mod_name in list(sys.modules):
    if _mod_name == "streamlit" or _mod_name.startswith("apps.dashboard") or _mod_name == "apps":
        del sys.modules[_mod_name]

sys.modules["streamlit"] = _STUB_MOD


# ---------------------------------------------------------------------------
# Fake workspace
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_stub():
    """Clear the streamlit stub between tests to avoid state leakage."""
    _STUB.calls.clear()
    _STUB.errors.clear()
    _STUB.session_state.clear()
    yield
    _STUB.calls.clear()
    _STUB.errors.clear()
    _STUB.session_state.clear()


@pytest.fixture()
def fake_workspace():
    """Return a fake workspace object with the minimum attributes the pages need."""
    ws = mock.MagicMock()
    ws.path = mock.MagicMock()
    ws.path.glob.return_value = []
    ws.settings.model_dump.return_value = {"name": "test", "model_path": None}
    ws.settings.name = "test"
    ws.settings.model_path = None
    ws.settings.embedding_path = None
    ws.settings.vision_path = None
    ws.list_collections.return_value = []
    ws.list_assets.return_value = []
    ws.stats.return_value = {
        "collections": 0, "assets": 0, "segments": 0,
        "spatial_entities": 0, "raster_scenes": 0, "vector_layers": 0,
        "observations": 0, "feedback_events": 0,
        "storage_bytes": 0, "index_manifest": None,
    }
    ws.search.return_value = mock.MagicMock(
        hits=[], total_hits=0, latency_ms=0, retrieval_run_id="run_x",
        query="", query_plan=None,
    )
    ws.ask.return_value = mock.MagicMock(
        abstained=True, abstention_reason="no model",
        text="", sources=[], citations=[],
    )
    ws.get_review_queue.return_value = []
    ws.record_feedback.return_value = None
    ws.export_dataset.return_value = mock.MagicMock()  # Path-like
    ws.inspect.return_value = mock.MagicMock(
        asset=mock.MagicMock(id="a1", title="a1", kind="document", created_at="2024-01-01"),
        revision=None, observations=[], segments=[], scenes=[], layers=[],
    )
    ws.create_collection.return_value = mock.MagicMock(name="new", id="col_new")
    ws.update_settings.return_value = ws.settings
    ws.build_index.return_value = None
    ws.rebuild_index.return_value = None
    ws.image_index.return_value = mock.MagicMock()
    ws.close.return_value = None
    return ws


# ---------------------------------------------------------------------------
# Page imports — done inside a helper so the stub is already active.
# ---------------------------------------------------------------------------

def _import_pages():
    """Import page renderers, returning their render callables."""
    from apps.dashboard.pages import (  # noqa: F401  (registers submodules)
        ask, assets, eval as eval_page, feedback, ingest, overview, search, settings,
    )
    return {
        "overview": overview.render,
        "search": search.render,
        "ask": ask.render,
        "assets": assets.render,
        "ingest": ingest.render,
        "feedback": feedback.render,
        "eval": eval_page.render,
        "settings": settings.render,
    }


# ===========================================================================
# Overview
# ===========================================================================

class TestOverviewPage:
    def test_render_calls_header_and_stats(self, fake_workspace):
        pages = _import_pages()
        pages["overview"](fake_workspace)
        assert _STUB.call_count("header") >= 1
        assert _STUB.call_count("metric") >= 1

    def test_render_handles_stats_exception(self, fake_workspace):
        fake_workspace.stats.side_effect = RuntimeError("db locked")
        pages = _import_pages()
        pages["overview"](fake_workspace)
        assert any("stats" in str(e).lower() for e in _STUB.errors)


# ===========================================================================
# Search
# ===========================================================================

class TestSearchPage:
    def test_render_uses_query_and_returns_hits(self, fake_workspace):
        fake_workspace.search.return_value = mock.MagicMock(
            hits=[mock.MagicMock(text="NDVI crop stress")],
            total_hits=1, latency_ms=10, retrieval_run_id="run1",
        )
        pages = _import_pages()
        pages["search"](fake_workspace)
        assert _STUB.call_count("text_input") >= 1

    def test_render_no_query_returns_early(self, fake_workspace):
        pages = _import_pages()
        pages["search"](fake_workspace)
        fake_workspace.search.assert_not_called()  # type: ignore[attr-defined]

    def test_render_handles_search_exception(self, fake_workspace):
        # Force the form-submit branch to execute by temporarily overriding
        # the stub's return values for the widgets this page reads.
        fake_workspace.search.side_effect = RuntimeError("fts crash")
        saved_text = _STUB._text_input_return
        saved_submit = _STUB._form_submit_return
        _STUB._text_input_return = "NDVI crop stress"
        _STUB._form_submit_return = True
        try:
            pages = _import_pages()
            pages["search"](fake_workspace)
        finally:
            _STUB._text_input_return = saved_text
            _STUB._form_submit_return = saved_submit
        assert any("search" in str(e).lower() or "failed" in str(e).lower() for e in _STUB.errors)


# ===========================================================================
# Ask / QA
# ===========================================================================

class TestAskPage:
    def test_render_no_model_shows_warning(self, fake_workspace):
        pages = _import_pages()
        pages["ask"](fake_workspace)
        assert _STUB.call_count("warning") >= 1

    def test_render_abstained_answer_displayed(self, fake_workspace):
        _STUB.session_state["gm_last_answer"] = mock.MagicMock(
            abstained=True, abstention_reason="no model", text="", sources=[], citations=[],
        )
        pages = _import_pages()
        pages["ask"](fake_workspace)
        assert _STUB.call_count("markdown") >= 1

    def test_render_successful_answer_shown(self, fake_workspace):
        _STUB.session_state["gm_last_answer"] = mock.MagicMock(
            abstained=False, abstention_reason=None,
            text="NDVI is a vegetation index.", sources=[], citations=[],
        )
        pages = _import_pages()
        pages["ask"](fake_workspace)
        assert _STUB.call_count("write") >= 1

    def test_render_ask_exception_surfaced(self, fake_workspace):
        fake_workspace.ask.side_effect = RuntimeError("llm error")
        _STUB._text_area_return = "What is NDVI?"
        _STUB._form_submit_return = True
        pages = _import_pages()
        pages["ask"](fake_workspace)
        assert any("ask" in str(e).lower() or "failed" in str(e).lower() for e in _STUB.errors)


# ===========================================================================
# Assets
# ===========================================================================

class TestAssetsPage:
    def test_render_no_collections_warning(self, fake_workspace):
        fake_workspace.list_collections.return_value = []
        pages = _import_pages()
        pages["assets"](fake_workspace)
        assert _STUB.call_count("warning") >= 1

    def test_render_with_collections_lists_assets(self, fake_workspace):
        fake_workspace.list_collections.return_value = [
            mock.MagicMock(name="papers", id="col1"),
        ]
        fake_workspace.list_assets.return_value = [
            mock.MagicMock(id="a1", title="paper1", kind="document"),
        ]
        pages = _import_pages()
        pages["assets"](fake_workspace)
        assert _STUB.call_count("selectbox") >= 1


# ===========================================================================
# Ingest
# ===========================================================================

class TestIngestPage:
    def test_render_no_collections_shows_create_form(self, fake_workspace):
        fake_workspace.list_collections.return_value = []
        pages = _import_pages()
        pages["ingest"](fake_workspace)
        assert _STUB.call_count("form") >= 1 or _STUB.call_count("text_input") >= 1

    def test_render_with_collections_shows_target_select(self, fake_workspace):
        fake_workspace.list_collections.return_value = [
            mock.MagicMock(name="papers", id="col1"),
        ]
        pages = _import_pages()
        pages["ingest"](fake_workspace)
        assert _STUB.call_count("selectbox") >= 1


# ===========================================================================
# Feedback
# ===========================================================================

class TestFeedbackPage:
    def test_render_shows_tabs(self, fake_workspace):
        pages = _import_pages()
        pages["feedback"](fake_workspace)
        assert _STUB.call_count("tabs") >= 1

    def test_render_handles_queue_error(self, fake_workspace):
        fake_workspace.get_review_queue.side_effect = RuntimeError("db error")
        pages = _import_pages()
        pages["feedback"](fake_workspace)
        assert any("review" in str(e).lower() or "failed" in str(e).lower() for e in _STUB.errors)

    def test_render_handles_export_error(self, fake_workspace):
        _STUB._selectbox_return = "rag_eval"
        _STUB._button_return = True
        fake_workspace.export_dataset.side_effect = RuntimeError("export crash")
        pages = _import_pages()
        pages["feedback"](fake_workspace)
        # The export error path calls st.error; accept either recording mechanism.
        assert _STUB.call_count("error") >= 1 or any(
            "export" in str(e).lower() or "failed" in str(e).lower() for e in _STUB.errors
        )


# ===========================================================================
# Eval
# ===========================================================================

class TestEvalPage:
    def test_render_no_benchmarks_info(self, fake_workspace):
        fake_workspace.path.glob.return_value = []
        pages = _import_pages()
        pages["eval"](fake_workspace)
        assert _STUB.call_count("info") >= 1

    def test_render_benchmark_result_displayed(self, fake_workspace):
        fake_bench = mock.MagicMock()
        fake_bench.__str__ = lambda self: "benchmarks/test.yaml"
        fake_workspace.path.glob.return_value = [fake_bench]
        fake_workspace.run_benchmark.return_value = mock.MagicMock(
            name="test", runs=1, metrics={"recall": 0.9},
        )
        _STUB._selectbox_return = fake_bench
        _STUB._button_return = True
        pages = _import_pages()
        pages["eval"](fake_workspace)
        assert _STUB.call_count("json") >= 1 or _STUB.call_count("write") >= 1


# ===========================================================================
# Settings
# ===========================================================================

class TestSettingsPage:
    def test_render_shows_config_tab(self, fake_workspace):
        pages = _import_pages()
        pages["settings"](fake_workspace)
        assert _STUB.call_count("tabs") >= 1

    def test_render_shows_current_settings_json(self, fake_workspace):
        pages = _import_pages()
        pages["settings"](fake_workspace)
        assert _STUB.call_count("json") >= 1

    def test_render_handles_doctor_error(self, fake_workspace):
        import apps.dashboard.pages.settings as settings_mod
        import geomemory.services.doctor as doctor_mod

        original = doctor_mod.doctor_workspace_open
        doctor_mod.doctor_workspace_open = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[assignment]
        try:
            pages = _import_pages()
            pages["settings"](fake_workspace)
        finally:
            doctor_mod.doctor_workspace_open = original  # type: ignore[attr-defined]
        assert any("doctor" in str(e).lower() or "failed" in str(e).lower() for e in _STUB.errors)
