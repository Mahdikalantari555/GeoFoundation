"""Tests for the dashboard shared library (apps/dashboard/lib.py).

These tests verify the pure helper functions without running Streamlit's
event loop. ``streamlit`` is replaced by a recording stub before any
dashboard module is imported.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Install the streamlit stub BEFORE any dashboard module is imported.
# ---------------------------------------------------------------------------

class _StCall:
    """Record every st.* call made during a test."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.session_state: dict[str, object] = {}
        self.errors: list[str] = []

    def __getattr__(self, name):
        def _record(*args, **kwargs):
            self.calls.append((name, args, kwargs))
            if name == "error":
                self.errors.append(args[0] if args else "")
            return self

        return _record

    def called_with(self, name: str, /, *args, **kwargs) -> bool:
        for call_name, call_args, call_kwargs in self.calls:
            if call_name == name and args == call_args and kwargs == call_kwargs:
                return True
        return False

    def call_count(self, name: str) -> int:
        return sum(1 for c, _, _ in self.calls if c == name)


# Global stub used by all tests in this module.
_STUB = _StCall()
_STUB_MOD = types.ModuleType("streamlit")
_STUB_MOD.session_state = _STUB.session_state
_STUB_MOD.error = lambda msg: _STUB.errors.append(msg) or None
for _attr in (
    "header", "caption", "info", "warning", "error", "success",
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

# Now that streamlit is stubbed, import dashboard helpers.
from apps.dashboard.lib import (  # noqa: E402
    close_workspace,
    get_workspace,
    open_or_create,
    run_guarded,
    set_workspace,
    workspace_exists,
)
from geomemory import GeoMemory  # noqa: E402


# ===========================================================================
# Workspace helpers
# ===========================================================================

class TestWorkspaceHelpers:
    def test_get_workspace_none_when_empty(self):
        assert get_workspace() is None

    def test_set_then_get_workspace(self):
        fake_ws = object()
        set_workspace(fake_ws)
        assert get_workspace() is fake_ws

    def test_close_workspace_clears_session(self):
        fake_ws = object()
        set_workspace(fake_ws)
        close_workspace()
        assert get_workspace() is None

    def test_workspace_exists_true_when_marker_present(self, tmp_path):
        root = tmp_path / "ws"
        root.mkdir()
        (root / ".geomemory").touch()
        assert workspace_exists(str(root)) is True

    def test_workspace_exists_false_without_marker(self, tmp_path):
        assert workspace_exists(str(tmp_path)) is False

    def test_workspace_exists_false_for_missing_path(self, tmp_path):
        assert workspace_exists(str(tmp_path / "no_such_dir")) is False

    def test_open_or_create_opens_existing(self, tmp_path):
        root = tmp_path / "open_ws"
        # Create a real workspace first, then open it.
        ws_create = GeoMemory.create(root)
        ws_create.close()
        ws = open_or_create(str(root), create=False)
        try:
            assert ws is not None
        finally:
            ws.close()

    def test_open_or_create_creates_new(self, tmp_path):
        root = tmp_path / "new_ws"
        ws = open_or_create(str(root), create=True)
        try:
            assert (root / ".geomemory").is_file()
        finally:
            ws.close()


# ===========================================================================
# run_guarded
# ===========================================================================

class TestRunGuarded:
    def test_returns_callable_result(self):
        def compute():
            return 42

        assert run_guarded(compute) == 42

    def test_surfaces_workspace_not_found(self):
        from geomemory import WorkspaceNotFoundError

        def boom():
            raise WorkspaceNotFoundError("nope")

        result = run_guarded(boom)
        assert result is None
        assert any("GeoMemory workspace" in e for e in _STUB.errors)

    def test_surfaces_generic_exception(self):
        def boom():
            raise RuntimeError("bad thing")

        result = run_guarded(boom, label="load")
        assert result is None
        assert any("load failed" in e for e in _STUB.errors)

    def test_passes_kwargs(self):
        def add(a, b):
            return a + b

        assert run_guarded(add, a=3, b=4) == 7
