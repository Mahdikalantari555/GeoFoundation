"""Shared helpers for the GeoMemory Streamlit dashboard.

Only the public :class:`geomemory.GeoMemory` API is used here. The dashboard
never touches SQLite, txtai, or repositories directly.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import streamlit as st

from geomemory import GeoMemory, WorkspaceNotFoundError


def get_workspace() -> GeoMemory | None:
    """Return the active workspace stored in Streamlit session state."""
    return st.session_state.get("gm_workspace")


def set_workspace(ws: GeoMemory | None) -> None:
    """Store the active workspace in session state."""
    st.session_state["gm_workspace"] = ws


def close_workspace() -> None:
    """Close and clear the active workspace."""
    ws = st.session_state.get("gm_workspace")
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass
    st.session_state["gm_workspace"] = None


def open_or_create(path: str, *, create: bool) -> GeoMemory:
    """Open an existing workspace or create a new one by path."""
    target = Path(path)
    if create:
        target.mkdir(parents=True, exist_ok=True)
        return GeoMemory.create(target)
    return GeoMemory.open(target)


def workspace_exists(path: str) -> bool:
    """Return True if the path is an existing GeoMemory workspace."""
    return (Path(path) / ".geomemory").is_file()


def run_guarded(fn: Callable[..., Any], *, label: str = "operation", **kwargs: Any) -> Any:
    """Execute a callable and surface a readable error instead of crashing."""
    try:
        return fn(**kwargs)
    except WorkspaceNotFoundError:
        st.error("The selected path is not a GeoMemory workspace. Open or create one from the sidebar.")
        return None
    except Exception as exc:  # noqa: BLE001 - surface backend errors in the UI
        st.error(f"{label} failed: {exc}")
        return None
