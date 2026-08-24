"""Feedback page — review queue, feedback export, and feedback listing."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import streamlit as st

from geomemory import GeoMemory
from geomemory.core.models import FeedbackEvent


def render(ws: GeoMemory) -> None:
    st.header("👍 Feedback")

    tab_review, tab_record, tab_export = st.tabs(["Review queue", "Record feedback", "Export dataset"])

    with tab_review:
        try:
            queue = ws.get_review_queue()
        except Exception as exc:  # noqa: BLE001
            st.error(f"Review queue failed: {exc}")
            return
        st.info("Review queue is empty.")
        for item in queue:
            with st.container(border=True):
                st.markdown(f"`{item.id}` · **{item.task_type}** · v{item.version}")
                c1, c2 = st.columns(2)
                if c1.button("Accept", key=f"acc_{item.id}"):
                    ws.review_example(item.id, accept=True)
                    st.rerun()
                if c2.button("Reject", key=f"rej_{item.id}"):
                    ws.review_example(item.id, accept=False)
                    st.rerun()

    with tab_record:
        with st.form("record_feedback"):
            target_type = st.selectbox("Target type", ["retrieval_run", "answer", "segment", "citation"])
            target_id = st.text_input("Target id")
            label = st.selectbox(
                "Label",
                [
                    "answer_rating",
                    "source_relevance",
                    "edited_answer",
                    "wrong_citation",
                    "hallucination",
                    "missing_result",
                ],
            )
            payload = st.text_area("Payload (JSON)", "{}")
            submitted = st.form_submit_button("Record")
        if submitted:
            try:
                payload_data = json.loads(payload or "{}")
            except json.JSONDecodeError:
                st.error("Invalid JSON payload.")
                return
            ws.record_feedback(
                FeedbackEvent(
                    target_type=target_type,
                    target_id=target_id,
                    label=label,
                    payload=payload_data,
                )
            )
            st.success("Feedback recorded.")

    with tab_export:
        task_type = st.selectbox("Task type", ["rag_eval", "qa_eval", "sft", "preference"])
        if st.button("Export dataset"):
            with tempfile.TemporaryDirectory() as tmp:
                try:
                    path = ws.export_dataset(task_type, tmp)
                    data = Path(path).read_bytes()
                    st.download_button(
                        label=f"Download {Path(path).name}",
                        data=data,
                        file_name=Path(path).name,
                        mime="application/octet-stream",
                    )
                except Exception as exc:  # noqa: BLE001
                    st.error(f"Export failed: {exc}")
