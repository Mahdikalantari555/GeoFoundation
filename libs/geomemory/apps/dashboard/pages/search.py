"""Search page — hybrid search with spatial, temporal, and sensor filters."""
from __future__ import annotations

import streamlit as st

from geomemory import GeoMemory
from geomemory.core.models import SearchFilters, SearchResult, SpatialFilter, TemporalFilter


def _collect_filters(ws: GeoMemory) -> SearchFilters | None:
    collections = ws.list_collections()
    col_names = {c.name: c.id for c in collections}
    sel = st.multiselect("Collections", list(col_names.keys()))
    sen = st.multiselect(
        "Sensors",
        ["Sentinel-2", "Sentinel-1", "Landsat-8", "Landsat-9", "MODIS"],
    )
    with st.expander("Spatial (bbox)"):
        c1, c2 = st.columns(2)
        min_lon = c1.number_input("min lon", -180.0, 180.0, 0.0, 0.1)
        min_lat = c2.number_input("min lat", -90.0, 90.0, 0.0, 0.1)
        max_lon = c1.number_input("max lon", -180.0, 180.0, 0.0, 0.1)
        max_lat = c2.number_input("max lat", -90.0, 90.0, 0.0, 0.1)
    with st.expander("Temporal"):
        date_from = st.text_input("Date from (YYYY-MM-DD)", "")
        date_to = st.text_input("Date to (YYYY-MM-DD)", "")

    spatial: SpatialFilter | None = None
    if min_lon != max_lon and min_lat != max_lat:
        try:
            spatial = SpatialFilter(op="intersects", bbox=(min_lon, min_lat, max_lon, max_lat))
        except Exception:  # noqa: BLE001
            spatial = None

    temporal: TemporalFilter | None = None
    if date_from or date_to:
        try:
            temporal = TemporalFilter(field="observed_at", from_=date_from or None, to=date_to or None)
        except Exception:  # noqa: BLE001
            temporal = None

    return SearchFilters(
        collections=[col_names[c] for c in sel] or None,
        sensors=list(sen) or None,
        spatial=spatial,
        temporal=temporal,
    )


def _apply_filters(
    ws: GeoMemory, filters: SearchFilters, *, query: str, top_k: int, top_n: int, mode: str
) -> SearchResult:
    return ws.search(
        query,
        mode=mode,
        top_k=top_k,
        top_n=top_n,
        collections=filters.collections,
        sensor=filters.sensors,
        spatial=filters.spatial,
        temporal=filters.temporal,
    )


def _render_result(result: SearchResult) -> None:
    results = result.hits
    if not results:
        st.info("No results.")
        return
    st.write(f"**{len(results)} hits** · {result.latency_ms} ms · run `{result.retrieval_run_id}`")

    for i, hit in enumerate(results):
        locator = (hit.locator or {}).get("file", "") if hit.locator else ""
        title = f"**[{i + 1}]** score=**{hit.score:.3f}**" + (" · `" + str(locator) + "`" if locator else "")
        with st.container(border=True):
            st.markdown(title)
            st.markdown(f"`{hit.metadata.get('segment_type', 'segment')}` · `{hit.id}`")
            snippet = (hit.text or "").strip()
            if len(snippet) > 500:
                snippet = snippet[:500] + "…"
            st.markdown(snippet or "*(no text)*")


def render(ws: GeoMemory) -> None:
    st.header("🔍 Search")
    with st.form("search_form"):
        query = st.text_input("Query", placeholder="e.g. NDVI changes in summer 2023")
        mode = st.selectbox("Mode", ["hybrid", "sparse", "dense"])
        c1, c2 = st.columns(2)
        top_k = c1.number_input("top_k", 1, 200, 20)
        top_n = c2.number_input("top_n", 1, 50, 5)
        submitted = st.form_submit_button("Search", type="primary")

    if not submitted or not query.strip():
        return

    filters = _collect_filters(ws)
    try:
        result = _apply_filters(ws, filters, query=query, top_k=top_k, top_n=top_n, mode=mode)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Search failed: {exc}")
        return

    _render_result(result)
