"""Assets page — list, inspect, and manage ingested assets per collection."""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from geomemory import GeoMemory


def _render_asset_detail(ws: GeoMemory, asset_id: str) -> None:
    try:
        detail = ws.inspect(asset_id)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Failed to inspect asset: {exc}")
        return

    asset = detail.asset
    st.subheader(f"Asset · {asset.title or asset.id}")
    c1, c2, c3 = st.columns(3)
    c1.write(f"**kind:** {asset.kind}")
    c2.write(f"**id:** `{asset.id}`")
    c3.write(f"**created:** {asset.created_at}")

    rev = detail.revision
    if rev is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("size", f"{rev.size_bytes} B")
        c2.metric("mime", rev.mime_type)
        c3.metric("segments", len(detail.segments))

    if detail.observations:
        st.subheader("Observations")
        for obs in detail.observations:
            st.write(f"- **{obs.metric}** = {obs.value} {obs.unit or ''}")

    if detail.segments:
        with st.expander(f"Segments ({len(detail.segments)})"):
            for seg in detail.segments:
                snippet = (seg.text or "").strip()
                if len(snippet) > 400:
                    snippet = snippet[:400] + "…"
                st.markdown(f"`{seg.segment_type}` · `{seg.id}`\n\n{snippet}")

    if detail.scenes:
        with st.expander(f"Raster scenes ({len(detail.scenes)})"):
            for scene in detail.scenes:
                st.write(
                    f"- sensor={scene.sensor}, crs={scene.crs}, bbox={scene.bbox}, "
                    f"acquired={scene.acquired_at}"
                )

    if detail.layers:
        with st.expander(f"Vector layers ({len(detail.layers)})"):
            for layer in detail.layers:
                st.write(
                    f"- `{layer.layer_name}` · driver={layer.driver} · feature_count={layer.feature_count}"
                )


def render(ws: GeoMemory) -> None:
    st.header("📦 Assets")

    collections = ws.list_collections()
    if not collections:
        st.warning("No collections exist yet. Ingest some data first.")
        return

    col_map = {c.name: c.id for c in collections}
    target = st.selectbox("Collection", list(col_map.keys()))

    try:
        assets = ws.list_assets(col_map[target])
    except Exception as exc:  # noqa: BLE001
        st.error(f"List failed: {exc}")
        return

    if not assets:
        st.info("No assets in this collection.")
        return

    selected = st.selectbox(
        "Inspect asset",
        [f"{a.title or a.id} ({a.kind})" for a in assets],
        index=0,
    )
    asset_id = assets[[f"{a.title or a.id} ({a.kind})" for a in assets].index(selected)].id

    _render_asset_detail(ws, asset_id)
