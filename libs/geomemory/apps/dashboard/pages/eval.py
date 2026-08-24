"""Eval page — run benchmarks and visualize retrieval/QA metrics."""
from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from geomemory import GeoMemory


def render(ws: GeoMemory) -> None:
    st.header("📈 Eval")

    st.subheader("Run benchmark")
    files = list(ws.path.glob("benchmarks/*.yaml")) + list(ws.path.glob("benchmarks/*.json"))
    if not files:
        st.info(
            "No benchmark files found. Place YAML/JSON benchmarks under "
            "`<workspace>/benchmarks/`."
        )
    else:
        bench = st.selectbox("Benchmark", files)
        if st.button("Run benchmark", type="primary"):
            with st.spinner("Running benchmark…"):
                try:
                    result = ws.run_benchmark(str(bench))
                    st.session_state["gm_last_benchmark"] = result
                    st.success("Benchmark complete.")
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Benchmark failed: {exc}")

    result = st.session_state.get("gm_last_benchmark")
    if result is None:
        return

    st.subheader("Last benchmark")
    st.write(f"**Benchmark:** {getattr(result, 'name', 'unknown')}")
    st.write(f"**Runs:** {getattr(result, 'runs', 0)}")

    metrics = getattr(result, "metrics", {})
    if metrics:
        st.json(metrics)
    else:
        st.caption("No metrics reported.")
