"""Ingest page — ingest files or raw text into a collection."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from geomemory import GeoMemory


def render(ws: GeoMemory) -> None:
    st.header("📥 Ingest")

    collections = ws.list_collections()
    if not collections:
        st.warning("No collections exist. Create one below to ingest files.")
        with st.form("new_collection_from_ingest"):
            name = st.text_input("New collection name", "papers")
            if st.form_submit_button("Create collection"):
                try:
                    ws.create_collection(name)
                    st.session_state["gm_ingest_new"] = name
                    st.rerun()
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Create failed: {exc}")

    if not collections and not st.session_state.get("gm_ingest_new"):
        return
    collections = ws.list_collections()
    col_map = {c.name: c.id for c in collections}
    target = st.selectbox("Target collection", list(col_map.keys()))

    mode = st.radio("Source", ["Upload file", "Paste text"], horizontal=True)

    if mode == "Upload file":
        uploaded = st.file_uploader(
            "Choose a file (.md, .txt, .py, .pdf, .docx, .tif, .geojson, .gpkg)",
            accept_multiple_files=True,
        )
        if uploaded:
            for f in uploaded:
                suffix = Path(f.name).suffix
                with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                    tmp.write(f.getbuffer())
                    tmp_path = tmp.name
                with st.spinner(f"Ingesting {f.name}…"):
                    try:
                        job = ws.ingest(tmp_path, collection_id=col_map[target])
                        st.session_state["gm_last_job"] = job
                        st.success(f"Ingested {f.name}")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Ingest failed for {f.name}: {exc}")
    else:
        text = st.text_area("Paste text", height=200)
        if st.button("Ingest text", type="primary"):
            if not text.strip():
                st.warning("Paste some text first.")
                return
            with tempfile.NamedTemporaryFile(delete=False, suffix=".md") as tmp:
                tmp.write(text.encode("utf-8"))
                tmp_path = tmp.name
            try:
                job = ws.ingest(tmp_path, collection_id=col_map[target])
                st.session_state["gm_last_job"] = job
                st.success("Text ingested.")
            except Exception as exc:  # noqa: BLE001
                st.error(f"Ingest failed: {exc}")

    job = st.session_state.get("gm_last_job")
    if job is not None:
        st.subheader("Last ingestion job")
        st.write(f"**state:** {job.state}")
        st.write(f"**asset_id:** {job.input.get('asset_id')}")
        st.write(f"**revision_id:** {job.input.get('revision_id')}")
