"""GeoMemory — Streamlit reference dashboard.

Run with::

    streamlit run apps/dashboard/app.py

Consumes only the public :class:`geomemory.GeoMemory` API.
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

import geomemory
from geomemory import GeoMemory

# Ensure pages package is importable regardless of cwd.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(_HERE))

from pages.ask import render as render_ask
from pages.assets import render as render_assets
from pages.eval import render as render_eval
from pages.feedback import render as render_feedback
from pages.ingest import render as render_ingest
from pages.overview import render as render_overview
from pages.search import render as render_search
from pages.settings import render as render_settings

st.set_page_config(
    page_title="GeoMemory",
    page_icon="🗺️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DEFAULT_ROOT = os.environ.get("GEOMEMORY_DASHBOARD_ROOT", "./workspace")


def _default_path() -> str:
    root = DEFAULT_ROOT
    if Path(root).is_dir() and (Path(root) / ".geomemory").is_file():
        return str(Path(root).resolve())
    return str(Path(root).resolve())


def _render_sidebar() -> None:
    """Workspace open/create controls in the sidebar."""
    with st.sidebar:
        st.title("GeoMemory")
        st.caption("Local spatiotemporal knowledge engine")

        path = st.text_input("Workspace path", value=_default_path())
        action = st.selectbox(
            "Action",
            ["Open existing", "Create new"],
        )
        submitted = st.button("Apply", type="primary", use_container_width=True)

        if submitted:
            try:
                if action == "Create new":
                    ws = GeoMemory.create(path)
                    st.session_state["gm_workspace"] = ws
                    st.success(f"Created workspace at {path}")
                    st.rerun()
                else:
                    ws = GeoMemory.open(path)
                    st.session_state["gm_workspace"] = ws
                    st.success(f"Opened workspace at {path}")
                    st.rerun()
            except FileExistsError:
                st.error("Workspace already exists. Use Open existing.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Operation failed: {exc}")

        ws = st.session_state.get("gm_workspace")
        if ws is not None:
            st.divider()
            settings = ws.settings
            st.metric("Workspace", settings.name)
            st.metric("Embedding", settings.embedding_path or "offline (n-gram)")
            st.metric("LLM", settings.model_path or "not configured")
            if st.button("Close workspace", use_container_width=True):
                try:
                    ws.close()
                except Exception:
                    pass
                st.session_state.pop("gm_workspace", None)
                st.rerun()

            if st.button("Use bundled models", use_container_width=True):
                try:
                    emb = "/mnt/data/LocalAI/Models/Embeddings/nomic-embed-text-v2-moe.Q8_0.gguf"
                    llm = "/mnt/data/LocalAI/Models/LLM/MiniCPM-V-4_6-Q8_0/MiniCPM-V-4_6-Q8_0.gguf"
                    ws.update_settings(
                        embedding_path=emb,
                        model_path=llm,
                    )
                    st.success("Bundled models configured.")
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Failed to set models: {exc}")

            st.divider()
            st.caption(f"geomemory {geomemory.__version__}")


def main() -> None:
    _render_sidebar()

    ws = st.session_state.get("gm_workspace")
    if ws is None:
        st.info("Open or create a workspace from the sidebar to get started.")
        return

    pages = {
        "📊 Overview": render_overview,
        "🔍 Search": render_search,
        "💬 Ask / QA": render_ask,
        "📥 Ingest": render_ingest,
        "📦 Assets": render_assets,
        "👍 Feedback": render_feedback,
        "📈 Eval": render_eval,
        "⚙️ Settings": render_settings,
    }
    choice = st.sidebar.radio("Navigate", list(pages.keys()), label_visibility="collapsed")
    pages[choice](ws)


if __name__ == "__main__":
    main()
