"""Overview page — workspace health and activity at a glance."""
from __future__ import annotations

import streamlit as st

from geomemory import GeoMemory


def render(ws: GeoMemory) -> None:
    st.header("📊 Overview")
    st.caption(f"Workspace **{ws.settings.name}**")

    try:
        stats = ws.stats()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to read workspace stats: {exc}")
        return

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Collections", stats.get("collections", 0))
    c2.metric("Assets", stats.get("assets", 0))
    c3.metric("Segments", stats.get("segments", 0))
    c4.metric("Spatial entities", stats.get("spatial_entities", 0))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Raster scenes", stats.get("raster_scenes", 0))
    c6.metric("Vector layers", stats.get("vector_layers", 0))
    c7.metric("Observations", stats.get("observations", 0))
    c8.metric("Feedback events", stats.get("feedback_events", 0))

    storage_bytes = stats.get("storage_bytes", 0)
    storage_mb = storage_bytes / (1024 * 1024)
    st.metric("Storage footprint", f"{storage_mb:.2f} MB")

    st.subheader("Index status")
    manifest = stats.get("index_manifest")
    if manifest:
        cols = st.columns(4)
        cols[0].write(f"**Space:** {manifest.get('space_id')}")
        cols[1].write(f"**Model:** {manifest.get('model_id')}")
        cols[2].write(f"**Dim:** {manifest.get('dimension')}")
        cols[3].write(f"**Docs:** {manifest.get('doc_count')}")
    else:
        st.info("No dense index manifest found. Build one from **Settings**.")

    st.subheader("Configured backends")
    bc1, bc2 = st.columns(2)
    bc1.write("**LLM (ask):** " + (ws.settings.model_path or "not configured — answers abstain"))
    bc2.write("**Embedding:** " + (ws.settings.embedding_path or "offline n-gram fallback"))

    st.subheader("Model/service availability")
    try:
        from geomemory.services.doctor import doctor_workspace_open
        report = doctor_workspace_open(ws.path)
        st.json(report)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Doctor failed: {exc}")
