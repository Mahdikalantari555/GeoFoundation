"""GeoMemory — Streamlit reference dashboard.

Run with::

    streamlit run apps/dashboard/app.py

Consumes only the public :class:`geomemory.GeoMemory` API.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st
from pages.ask import render as render_ask
from pages.assets import render as render_assets
from pages.eval import render as render_eval
from pages.feedback import render as render_feedback
from pages.ingest import render as render_ingest
from pages.overview import render as render_overview
from pages.search import render as render_search
from pages.settings import render as render_settings

from geomemory import GeoMemory

st.set_page_config(
    page_title="GeoMemory",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_ROOT = os.environ.get("GEOMEMORY_DASHBOARD_ROOT", "./workspace")


def _render_sidebar() -> None:
    """Workspace open/create controls in the sidebar."""
    with st.sidebar:
        st.title("🗺️ GeoMemory")
        st.caption("Local spatiotemporal knowledge engine")

        path = st.text_input("Workspace path", value=DEFAULT_ROOT)
        action = st.radio(
            "Workspace action",
            ("Open existing", "Create new"),
            horizontal=True,
        )
        submitted = st.button("Open workspace", type="primary", use_container_width=True)

        if submitted and action == "Create new":
            Path(path).mkdir(parents=True, exist_ok=True)
            try:
                ws = GeoMemory.create(path)
                st.session_state["gm_workspace"] = ws
                st.success(f"Created workspace at {path}")
                st.rerun()
            except Exception as exc:  # noqa: BLE001
                st.error(f"Create failed: {exc}")
        elif submitted:
            try:
                ws = GeoMemory.open(path)
                st.session_state["gm_workspace"] = ws
                st.success(f"Opened workspace at {path}")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Open failed: {exc}")
                st.info("Use 'Create new' if this directory has no workspace yet.")

        ws = st.session_state.get("gm_workspace") or GeoMemory(path) if False else st.session_state.get(
            "gm_workspace"
        )
        if ws is not None:
            st.divider()
            settings = ws.settings
            st.metric("Workspace", settings.name)
            st.metric("Embedding model", settings.embedding_path or "offline (n-gram)")
            st.metric("LLM model", settings.model_path or "not configured")
            if st.button("Close workspace", use_container_width=True):
                ws.close()
                st.session_state.pop("gm_workspace", None)
                st.rerun()

        st.divider()
        st.caption(f"geomemory·{__import__('geomemory').__version__}")


def main() -> None:
    _render_sidebar()

    ws = st.session_state.get("gm_workspace")
    if ws is None:
        st.info("Open or create a workspace from the sidebar to begin.")
        st.stop()

    pages = {
        "📊 Overview": render_overview,
        "🔍 Search": render_search,
        "💬 Ask / QA": render_ask,
        "🗂️ Assets": render_assets,
        "📥 Ingest": render_ingest,
        "👍 Feedback": render_feedback,
        "📈 Eval": render_eval,
        "⚙️ Settings": render_settings,
    }
    choice = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")
    pages[choice](ws)


main()
